import numpy as np


class Geometry:

    def __init__(self, width: int, height: int, mpp: float | tuple[float, float], origin=(0.0, 0.0)):
        """
        Pixel grid geometry.

        Parameters
        ----------
        width:
            Number of columns.
        height:
            Number of rows.
        mpp:
            Microns per pixel. A scalar applies to both axes.
        origin:
            Physical coordinate of pixel ``(0, 0)``.

        Attributes
        ----------
        width: int
            Number of columns.
        height: int
            Number of rows.
        mpp: np.ndarray
            Microns per pixel for ``x`` and ``y`` axes.
        origin: np.ndarray
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
        matrix:
            Homogeneous transform matrix with shape ``(3, 3)``.

        Attributes
        ----------
        matrix: np.ndarray
            Homogeneous transform matrix.
        """
        self.matrix = np.eye(3, dtype=np.float64) if matrix is None else np.asarray(matrix, dtype=np.float64)

    def __matmul__(self, other: 'Transform') -> 'Transform':
        return Transform(self.matrix @ other.matrix)

    def inverse(self) -> 'Transform':
        return Transform(np.linalg.inv(self.matrix))

    def apply(self, points):
        points = np.asarray(points, dtype=np.float64)
        homogeneous = np.column_stack([points, np.ones(len(points), dtype=np.float64)])
        transformed = homogeneous @ self.matrix.T
        return transformed[:, :2] / transformed[:, [2]]

    @classmethod
    def identity(cls) -> 'Transform':
        return cls()

    @classmethod
    def translation(cls, x: float, y: float) -> 'Transform':
        return cls([
            [1, 0, x],
            [0, 1, y],
            [0, 0, 1],
        ])

    @classmethod
    def rotation(cls, angle: float, center=(0.0, 0.0)) -> 'Transform':
        cosine = np.cos(angle)
        sine = np.sin(angle)
        x, y = center
        return cls.translation(x, y) @ cls([
            [cosine, -sine, 0],
            [sine, cosine, 0],
            [0, 0, 1],
        ]) @ cls.translation(-x, -y)

    @classmethod
    def scale(cls, factor: float, center=(0.0, 0.0)) -> 'Transform':
        x, y = center
        return cls.translation(x, y) @ cls([
            [factor, 0, 0],
            [0, factor, 0],
            [0, 0, 1],
        ]) @ cls.translation(-x, -y)
