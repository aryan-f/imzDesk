import copy

import numpy as np
from scipy import sparse
from sklearn import decomposition, manifold

from imzdesk.core import DImage, RImage, SImage
from imzdesk.transforms.base import Transform


class Compose(Transform):

    def __init__(self, transforms):
        """
        Initialize an ordered sequence of transforms.

        Parameters
        ----------
        transforms : sequence of callable
            Callable transforms applied in order.
        """
        self.transforms = list(transforms)

    def __call__(self, image):
        """
        Apply each transform in sequence to an image-like value.
        """
        for transform in self.transforms:
            image = transform(image)
        return image


class Normalize(Transform):

    def __init__(self, method='tic'):
        """
        Initialize per-spectrum normalization for a ragged image.

        Parameters
        ----------
        method : str, optional
            Normalization method. Supported values are ``'none'``, ``'tic'``,
            ``'rms'``, ``'median'``, ``'max'``, and ``'log1p'``.

        """
        self.method = method

    def __call__(self, image):
        """
        Normalize every spectrum in a ragged image.

        Parameters
        ----------
        image : RImage
            Ragged image to normalize.

        Returns
        -------
        RImage
            Shallow image copy containing normalized values.
        """
        method = 'none' if self.method is None else self.method.lower()
        normalized = copy.copy(image)
        if method == 'none':
            normalized.values = image.values.copy()
            return normalized
        values = image.values.astype(np.float32, copy=True)
        if method == 'log1p':
            normalized.values = np.log1p(values)
            return normalized
        for pixel_index in range(len(image)):
            pixel_start = image.offsets[pixel_index]
            pixel_stop = image.offsets[pixel_index + 1]
            pixel_values = values[pixel_start:pixel_stop]
            if pixel_values.size == 0:
                continue
            if method == 'tic':
                normalizer = pixel_values.sum(dtype=np.float64)
            elif method == 'rms':
                normalizer = np.sqrt(np.mean(np.square(pixel_values, dtype=np.float64)))
            elif method == 'median':
                normalizer = np.median(pixel_values)
            else:
                normalizer = pixel_values.max()
            if normalizer > 0:
                values[pixel_start:pixel_stop] = pixel_values / normalizer
        normalized.values = values
        return normalized


class Bin(Transform):

    def __init__(self, minimum_channel=50.0, maximum_channel=1000.0, bin_width=2.0):
        """
        Initialize binning from ragged spectra to rectangular sparse features.

        Parameters
        ----------
        minimum_channel : float, default=50.0
            Inclusive lower channel bound.
        maximum_channel : float, default=1000.0
            Exclusive upper channel bound.
        bin_width : float, default=2.0
            Width of each channel bin.

        """
        self.minimum_channel = minimum_channel
        self.maximum_channel = maximum_channel
        self.bin_width = bin_width

    def __call__(self, image):
        """
        Bin ragged spectra into a shared sparse feature matrix.

        Parameters
        ----------
        image : RImage
            Ragged image to bin.

        Returns
        -------
        SImage
            Sparse rectangular image over the configured bins.
        """
        bin_edges = np.arange(self.minimum_channel, self.maximum_channel + self.bin_width, self.bin_width, dtype=np.float64)
        number_of_bins = bin_edges.size - 1
        feature_rows = []
        feature_columns = []
        feature_values = []
        for pixel_index in range(len(image)):
            positions, values = image.pixel(pixel_index)
            within_channel_range = (positions >= self.minimum_channel) & (positions < self.maximum_channel)
            if not within_channel_range.any():
                continue
            bin_indices = np.floor((positions[within_channel_range] - self.minimum_channel) / self.bin_width).astype(np.int64)
            bin_sort_order = np.argsort(bin_indices)
            sorted_bin_indices = bin_indices[bin_sort_order]
            sorted_values = values[within_channel_range][bin_sort_order]
            occupied_bins, occupied_bin_starts = np.unique(sorted_bin_indices, return_index=True)
            summed_bin_values = np.add.reduceat(sorted_values, occupied_bin_starts)
            feature_rows.extend([pixel_index] * occupied_bins.size)
            feature_columns.extend(occupied_bins.tolist())
            feature_values.extend(summed_bin_values.tolist())
        binned_features = sparse.csr_matrix(
            (np.asarray(feature_values, dtype=np.float32), (feature_rows, feature_columns)),
            shape=(len(image), number_of_bins),
            dtype=np.float32,
        )
        return SImage(
            values=binned_features,
            coordinates=image.coordinates.copy(),
        )


class ToDense(Transform):
    """
    Convert a sparse image with rectangular features into a dense image.
    """

    def __call__(self, image):
        """
        Convert a sparse rectangular image to dense storage.

        Parameters
        ----------
        image : SImage or DImage
            Image to convert.

        Returns
        -------
        DImage
            Dense image, or the unchanged input when already dense.
        """
        if isinstance(image, DImage):
            return image
        return DImage(
            values=image.values.toarray(),
            coordinates=image.coordinates.copy(),
        )


class Scale(Transform):

    def __init__(self, method='robust'):
        """
        Initialize feature scaling across measured pixels.

        Parameters
        ----------
        method : {'robust', 'minmax', 'zscore'}, default='robust'
            Scaling method. Supported values are ``'robust'`` (median and
            interquartile range), ``'minmax'``, and ``'zscore'``.

        """
        self.method = method

    def __call__(self, image):
        """
        Scale features across all measured pixels.

        Parameters
        ----------
        image : SImage or DImage
            Rectangular image to scale.

        Returns
        -------
        SImage or DImage
            Scaled image with the same storage representation.
        """
        if isinstance(image, SImage):
            return self._scale_sparse(image)

        values = np.asarray(image.values, dtype=np.float32)
        scalar = values.ndim == 1
        features = values[:, None] if scalar else values

        match self.method.lower():
            case 'robust':
                center = np.nanmedian(features, axis=0)
                lower, upper = np.nanpercentile(features, [25, 75], axis=0)
                scale = upper - lower
            case 'minmax':
                center = np.nanmin(features, axis=0)
                scale = np.nanmax(features, axis=0) - center
            case 'zscore':
                center = np.nanmean(features, axis=0)
                scale = np.nanstd(features, axis=0)
            case other:
                raise ValueError(f'Unknown scaling method: {other}')

        scale = np.where(np.isfinite(scale) & (scale != 0), scale, 1)
        scaled = (features - center) / scale
        if scalar:
            scaled = scaled[:, 0]
        return DImage(values=scaled, coordinates=image.coordinates.copy())

    def _scale_sparse(self, image):
        """
        Apply min-max scaling without densifying a sparse image.

        Parameters
        ----------
        image : SImage
            Sparse rectangular image.

        Returns
        -------
        SImage
            Min-max scaled sparse image.
        """
        if self.method.lower() != 'minmax':
            raise ValueError('Sparse images only support min-max scaling.')

        values = image.values.astype(np.float32).tocsc(copy=True)
        if values.data.size and np.nanmin(values.data) < 0:
            raise ValueError('Sparse min-max scaling requires nonnegative values.')

        minimums = values.min(axis=0).toarray().ravel()
        maximums = values.max(axis=0).toarray().ravel()
        ranges = maximums - minimums
        scales = np.where(np.isfinite(ranges) & (ranges != 0), ranges, 1)

        for column in np.flatnonzero(minimums):
            start, stop = values.indptr[column:column + 2]
            values.data[start:stop] -= minimums[column]
        values = values @ sparse.diags(1 / scales, format='csc')
        values.eliminate_zeros()
        return SImage(values=values.tocsr(), coordinates=image.coordinates.copy())


class TIC(Transform):
    """
    Sum each pixel's feature vector into one intensity value.
    """

    def __call__(self, sparse_image):
        """
        Sum every sparse feature vector into total ion current.

        Parameters
        ----------
        sparse_image : SImage
            Sparse rectangular image.

        Returns
        -------
        DImage
            Scalar total ion current per pixel.
        """
        return DImage(
            values=np.asarray(sparse_image.values.sum(axis=1)).ravel(),
            coordinates=sparse_image.coordinates.copy(),
        )


class PCA(Transform):

    def __init__(self, number_of_components=3, random_seed=0):
        """
        Reduce dense images with principal component analysis.

        Parameters
        ----------
        number_of_components : int, default=3
            Number of principal components to return.
        random_seed : int, default=0
            Seed used by randomized PCA.

        """
        self.number_of_components = number_of_components
        self.random_seed = random_seed

    def __call__(self, dense_image):
        """
        Project dense features onto their principal components.

        Parameters
        ----------
        dense_image : DImage
            Dense rectangular image.

        Returns
        -------
        DImage
            Principal component scores and source coordinates.
        """
        values = decomposition.PCA(
            n_components=self.number_of_components,
            svd_solver='randomized',
            random_state=self.random_seed,
        ).fit_transform(dense_image.values)
        return DImage(values=values, coordinates=dense_image.coordinates.copy())


class NMF(Transform):

    def __init__(self, number_of_components=3, random_seed=0):
        """
        Reduce sparse or dense images with non-negative matrix factorization.

        Parameters
        ----------
        number_of_components : int, default=3
            Number of NMF components to return.
        random_seed : int, default=0
            Seed used by the NMF initializer.

        """
        self.number_of_components = number_of_components
        self.random_seed = random_seed

    def __call__(self, image):
        """
        Factor nonnegative image features into component scores.

        Parameters
        ----------
        image : SImage or DImage
            Nonnegative rectangular image.

        Returns
        -------
        DImage
            Nonnegative component scores and source coordinates.
        """
        values = decomposition.NMF(
            n_components=self.number_of_components,
            init='nndsvda',
            max_iter=300,
            random_state=self.random_seed,
        ).fit_transform(image.values)
        return DImage(values=values, coordinates=image.coordinates.copy())


class TSNE(Transform):

    def __init__(self, number_of_components=3, random_seed=0):
        """
        Reduce dense images with t-SNE after PCA preprojection.

        Parameters
        ----------
        number_of_components : int, default=3
            Number of t-SNE dimensions to return.
        random_seed : int, default=0
            Seed used by PCA preprojection and t-SNE.

        """
        self.number_of_components = number_of_components
        self.random_seed = random_seed

    def __call__(self, dense_image):
        """
        Embed dense features with PCA followed by t-SNE.

        Parameters
        ----------
        dense_image : DImage
            Dense rectangular image.

        Returns
        -------
        DImage
            t-SNE coordinates and source spatial coordinates.
        """
        pca_projection = decomposition.PCA(
            n_components=32, random_state=self.random_seed
        ).fit_transform(dense_image.values)
        values = manifold.TSNE(
            n_components=self.number_of_components,
            init='pca',
            learning_rate='auto',
            perplexity=30,
            max_iter=750,
            random_state=self.random_seed,
        ).fit_transform(pca_projection)
        return DImage(values=values, coordinates=dense_image.coordinates.copy())


class Project(Transform):

    def __init__(self, number_of_components=8, tissue_fraction=0.1, background_fraction=0.1):
        """
        Project dense features onto a tissue/background direction.

        Parameters
        ----------
        number_of_components : int, default=8
            Number of leading PCA components used to identify high-energy
            tissue seeds.
        tissue_fraction : float, default=0.1
            Fraction of pixels used as tissue seeds.
        background_fraction : float, default=0.1
            Corner fraction used as background seeds.

        """
        self.number_of_components = number_of_components
        self.tissue_fraction = tissue_fraction
        self.background_fraction = background_fraction

    def __call__(self, image):
        """
        Project dense features onto a tissue-background direction.

        Parameters
        ----------
        image : DImage
            Dense embedding image.

        Returns
        -------
        DImage
            Scalar tissue-likelihood image.
        """
        values = np.asarray(image.values, dtype=np.float32)
        number_of_components = min(self.number_of_components, values.shape[1], len(values))
        projected = decomposition.PCA(n_components=number_of_components, random_state=0).fit_transform(values)
        energy = np.linalg.norm(projected, axis=1)
        tissue_count = max(1, round(len(values) * self.tissue_fraction))
        tissue_indices = np.argsort(energy)[-tissue_count:]
        coordinates = image.coordinates
        x_limit = coordinates[:, 0].min() + (coordinates[:, 0].max() - coordinates[:, 0].min()) * self.background_fraction
        y_limit = coordinates[:, 1].min() + (coordinates[:, 1].max() - coordinates[:, 1].min()) * self.background_fraction
        background_indices = np.flatnonzero((coordinates[:, 0] <= x_limit) & (coordinates[:, 1] <= y_limit))
        if background_indices.size == 0:
            background_count = max(1, round(len(values) * self.tissue_fraction))
            background_indices = np.argsort(energy)[:background_count]
        direction = values[tissue_indices].mean(axis=0) - values[background_indices].mean(axis=0)
        direction_norm = np.linalg.norm(direction)
        if direction_norm > 0:
            direction = direction / direction_norm
        scores = values @ direction
        if scores[background_indices].mean() > scores[tissue_indices].mean():
            scores = -scores
        scores = scores - scores.min()
        if scores.max() > 0:
            scores = scores / scores.max()
        return DImage(scores, image.coordinates.copy())
