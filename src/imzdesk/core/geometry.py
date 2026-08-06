import numpy as np


class Geometry:

    def __init__(self, width, height, mpp, origin=(0.0, 0.0)):
        """
        Pixel grid geometry.

        Parameters
        ----------
        width : int
            Number of columns.
        height : int
            Number of rows.
        mpp : float or tuple of float
            Microns per pixel. A scalar applies to both axes.
        origin : tuple of float, default=(0.0, 0.0)
            Physical coordinate of pixel ``(0, 0)``.

        """
        self.width = width
        self.height = height
        self.mpp = np.asarray(mpp if isinstance(mpp, tuple) else (mpp, mpp), dtype=np.float64)
        self.origin = np.asarray(origin, dtype=np.float64)


class Transform:

    def __init__(self, matrix=None):
        """
        Two-dimensional homogeneous transform.

        Parameters
        ----------
        matrix : array-like, optional
            Homogeneous transform matrix with shape ``(3, 3)``.
        """
        self.matrix = np.eye(3, dtype=np.float64) if matrix is None else np.asarray(matrix, dtype=np.float64)

    def __matmul__(self, other):
        """
        Compose this transform with another transform.

        Parameters
        ----------
        other : Transform
            Transform applied before this transform.

        Returns
        -------
        Transform
            Composed transform.
        """
        return Transform(self.matrix @ other.matrix)

    def inverse(self):
        """
        Return the inverse transform.

        Returns
        -------
        Transform
            Inverted transform.
        """
        return Transform(np.linalg.inv(self.matrix))

    def apply(self, points):
        """
        Apply the transform to an array of two-dimensional points.

        Parameters
        ----------
        points : array-like
            Points with shape ``(n_points, 2)``.

        Returns
        -------
        numpy.ndarray
            Transformed points.
        """
        points = np.asarray(points, dtype=np.float64)
        homogeneous = np.column_stack([points, np.ones(len(points), dtype=np.float64)])
        transformed = homogeneous @ self.matrix.T
        return transformed[:, :2] / transformed[:, [2]]

    @classmethod
    def identity(cls):
        """
        Construct an identity transform.

        Returns
        -------
        Transform
            Identity transform.
        """
        return cls()

    @classmethod
    def translation(cls, x, y):
        """
        Construct a two-dimensional translation transform.

        Parameters
        ----------
        x : float
            Horizontal displacement.
        y : float
            Vertical displacement.

        Returns
        -------
        Transform
            Translation transform.
        """
        return cls([
            [1, 0, x],
            [0, 1, y],
            [0, 0, 1],
        ])

    @classmethod
    def rotation(cls, angle, center=(0.0, 0.0)):
        """
        Construct a rotation transform around a center point.

        Parameters
        ----------
        angle : float
            Counterclockwise angle in radians.
        center : tuple of float, default=(0.0, 0.0)
            Rotation center.

        Returns
        -------
        Transform
            Rotation transform.
        """
        cosine = np.cos(angle)
        sine = np.sin(angle)
        x, y = center
        return cls.translation(x, y) @ cls([
            [cosine, -sine, 0],
            [sine, cosine, 0],
            [0, 0, 1],
        ]) @ cls.translation(-x, -y)

    @classmethod
    def scale(cls, factor, center=(0.0, 0.0)):
        """
        Construct a scale transform around a center point.

        Parameters
        ----------
        factor : float or tuple of float
            Axis-wise scale factors.
        center : tuple of float, default=(0.0, 0.0)
            Scale center.

        Returns
        -------
        Transform
            Scale transform.
        """
        factors = factor if isinstance(factor, tuple) else (factor, factor)
        x, y = center
        return cls.translation(x, y) @ cls([
            [factors[0], 0, 0],
            [0, factors[1], 0],
            [0, 0, 1],
        ]) @ cls.translation(-x, -y)
