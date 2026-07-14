import copy

import numpy as np
from scipy import sparse
from sklearn import decomposition, manifold

from imzdesk.core import DImage, RImage, SImage
from imzdesk.transforms.base import Transform


class Compose(Transform):

    def __init__(self, transforms):
        """
        Chain several transforms.

        Parameters
        ----------
        transforms:
            Callable transforms applied in order.

        Attributes
        ----------
        transforms: list
            Callable transforms applied in order.
        """
        self.transforms = list(transforms)

    def __call__(self, image):
        for transform in self.transforms:
            image = transform(image)
        return image


class Normalize(Transform):

    def __init__(self, method: str | None = 'tic'):
        """
        Normalize sparse pixel values.

        Parameters
        ----------
        method:
            Normalization method. Supported values are ``'none'``, ``'tic'``,
            ``'rms'``, ``'median'``, ``'max'``, and ``'log1p'``.

        Attributes
        ----------
        method: str | None
            Normalization method.
        """
        self.method = method

    def __call__(self, image: RImage) -> RImage:
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

    def __init__(self, minimum_channel: float = 50.0, maximum_channel: float = 1000.0, bin_width: float = 2.0):
        """
        Bin ragged sparse pixels into rectangular sparse features.

        Parameters
        ----------
        minimum_channel:
            Inclusive lower channel bound.
        maximum_channel:
            Exclusive upper channel bound.
        bin_width:
            Width of each channel bin.

        Attributes
        ----------
        minimum_channel: float
            Inclusive lower channel bound.
        maximum_channel: float
            Exclusive upper channel bound.
        bin_width: float
            Width of each channel bin.
        """
        self.minimum_channel = minimum_channel
        self.maximum_channel = maximum_channel
        self.bin_width = bin_width

    def __call__(self, image: RImage) -> SImage:
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

    def __call__(self, image: SImage | DImage) -> DImage:
        if isinstance(image, DImage):
            return image
        return DImage(
            values=image.values.toarray(),
            coordinates=image.coordinates.copy(),
        )


class TIC(Transform):
    """
    Sum each pixel's feature vector into one intensity value.
    """

    def __call__(self, sparse_image: SImage) -> DImage:
        return DImage(
            values=np.asarray(sparse_image.values.sum(axis=1)).ravel(),
            coordinates=sparse_image.coordinates.copy(),
        )


class PCA(Transform):

    def __init__(self, number_of_components: int = 3, random_seed: int = 0):
        """
        Reduce dense images with principal component analysis.

        Parameters
        ----------
        number_of_components:
            Number of principal components to return.
        random_seed:
            Seed used by randomized PCA.

        Attributes
        ----------
        number_of_components: int
            Number of principal components to return.
        random_seed: int
            Seed used by randomized PCA.
        """
        self.number_of_components = number_of_components
        self.random_seed = random_seed

    def __call__(self, dense_image: DImage) -> DImage:
        values = decomposition.PCA(
            n_components=self.number_of_components,
            svd_solver='randomized',
            random_state=self.random_seed,
        ).fit_transform(dense_image.values)
        return DImage(values=values, coordinates=dense_image.coordinates.copy())


class NMF(Transform):

    def __init__(self, number_of_components: int = 3, random_seed: int = 0):
        """
        Reduce sparse or dense images with non-negative matrix factorization.

        Parameters
        ----------
        number_of_components:
            Number of NMF components to return.
        random_seed:
            Seed used by the NMF initializer.

        Attributes
        ----------
        number_of_components: int
            Number of NMF components to return.
        random_seed: int
            Seed used by the NMF initializer.
        """
        self.number_of_components = number_of_components
        self.random_seed = random_seed

    def __call__(self, image: SImage | DImage) -> DImage:
        values = decomposition.NMF(
            n_components=self.number_of_components,
            init='nndsvda',
            max_iter=300,
            random_state=self.random_seed,
        ).fit_transform(image.values)
        return DImage(values=values, coordinates=image.coordinates.copy())


class TSNE(Transform):

    def __init__(self, number_of_components: int = 3, random_seed: int = 0):
        """
        Reduce dense images with t-SNE after PCA preprojection.

        Parameters
        ----------
        number_of_components:
            Number of t-SNE dimensions to return.
        random_seed:
            Seed used by PCA preprojection and t-SNE.

        Attributes
        ----------
        number_of_components: int
            Number of t-SNE dimensions to return.
        random_seed: int
            Seed used by PCA preprojection and t-SNE.
        """
        self.number_of_components = number_of_components
        self.random_seed = random_seed

    def __call__(self, dense_image: DImage) -> DImage:
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

    def __init__(self, number_of_components: int = 8, tissue_fraction: float = 0.1, background_fraction: float = 0.1):
        """
        Project dense features onto a tissue/background direction.

        Parameters
        ----------
        number_of_components:
            Number of leading PCA components used to identify high-energy
            tissue seeds.
        tissue_fraction:
            Fraction of pixels used as tissue seeds.
        background_fraction:
            Corner fraction used as background seeds.

        Attributes
        ----------
        number_of_components: int
            Number of leading PCA components.
        tissue_fraction: float
            Fraction of pixels used as tissue seeds.
        background_fraction: float
            Corner fraction used as background seeds.
        """
        self.number_of_components = number_of_components
        self.tissue_fraction = tissue_fraction
        self.background_fraction = background_fraction

    def __call__(self, image: DImage) -> DImage:
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
