from copy import deepcopy
from typing import Tuple

import pytest
import torch
from torch import Tensor

from deepali.core import ALIGN_CORNERS, Grid, functional as U
from deepali.data import Image, ImageBatch


def image_size(sdim: int) -> Tuple[int, ...]:
    if sdim == 2:
        return (64, 57)
    if sdim == 3:
        return (64, 57, 31)
    raise ValueError("image_size() 'sdim' must be 2 or 3")


def image_shape(sdim: int) -> Tuple[int, ...]:
    return tuple(reversed(image_size(sdim)))


@pytest.fixture(scope="function")
def grid(request) -> Tensor:
    size = image_size(request.param)
    spacing = (0.25, 0.2, 0.5)[: len(size)]
    return Grid(size=size, spacing=spacing)


@pytest.fixture(scope="function")
def data(request) -> Tensor:
    shape = image_shape(request.param)
    return torch.randn((1,) + shape).mul_(100)


@pytest.fixture(scope="function")
def zeros(request) -> Tensor:
    shape = image_shape(request.param)
    return torch.zeros((1,) + shape)


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_init(zeros: Tensor, grid: Grid) -> None:

    data = zeros

    image = Image(data)
    assert type(image) is Image
    assert hasattr(image, "_grid")
    assert isinstance(image._grid, Grid)
    assert image._grid.size() == grid.size()
    assert image.data_ptr() == data.data_ptr()
    tensor = image.tensor()
    assert type(tensor) is Tensor
    assert image.data_ptr() == tensor.data_ptr()

    image = Image(data, grid, device=data.device)
    assert type(image) is Image
    assert hasattr(image, "_grid")
    assert image._grid is grid
    assert image.data_ptr() == data.data_ptr()

    image = Image(data, grid, requires_grad=True)
    assert type(image) is Image
    assert image._grid is grid
    assert image.requires_grad
    assert not image.is_pinned()
    assert image.device == data.device
    assert image.dtype == data.dtype
    assert image.data_ptr() == data.data_ptr()

    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        image = Image(data, grid, device=device)
        assert type(image) is Image
        assert image._grid is grid
        assert image.data_ptr() != data.data_ptr()
        assert image.is_cuda
        assert image.device == device
        assert image.dtype == data.dtype

        image = Image(data, grid, pin_memory=True)
        assert type(image) is Image
        assert image._grid is grid
        assert not image.requires_grad
        assert image.is_pinned()
        assert image.device == data.device
        assert image.dtype == data.dtype
        assert image.data_ptr() != data.data_ptr()

        image = Image(data, grid, requires_grad=True, pin_memory=True)
        assert type(image) is Image
        assert image._grid is grid
        assert image.requires_grad
        assert image.is_pinned()
        assert image.device == data.device
        assert image.dtype == data.dtype
        assert image.data_ptr() != data.data_ptr()

    params = torch.zeros((1, 32, 64, 64), requires_grad=True)
    assert params.requires_grad

    image = Image(params)
    assert type(image) is Image
    assert image.requires_grad
    assert image.data_ptr() == params.data_ptr()

    image = Image(params, requires_grad=False)
    assert type(image) is Image
    assert not image.requires_grad
    assert image.data_ptr() == params.data_ptr()


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (3,)], indirect=True)
def test_image_deepcopy(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    other = deepcopy(image)
    assert type(other) is Image
    assert hasattr(other, "_grid")
    assert other.grid() is not image.grid()
    assert other.grid() == image.grid()
    assert other.data_ptr() != image.data_ptr()


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (3,)], indirect=True)
def test_image_torch_function(zeros: Tensor, grid: Grid) -> None:
    data = zeros

    image = Image(data, grid)
    assert type(image) is Image
    assert hasattr(image, "_grid")
    assert image.grid() is grid

    result = image.type(torch.int16)
    assert type(result) is Image
    assert hasattr(result, "_grid")
    assert result.grid() is image.grid()
    assert result.dtype is torch.int16
    assert result.data_ptr() != image.data_ptr()

    result = image.eq(0)
    assert type(result) is Image
    assert hasattr(result, "_grid")
    assert result.grid() is image.grid()
    assert result.dtype is torch.bool
    assert result.data_ptr() != image.data_ptr()

    result = result.all()
    assert type(result) is Tensor
    assert not hasattr(result, "_grid")
    assert result.ndim == 0
    assert result.item() is True

    result = torch.add(image, 2)
    assert type(result) is Image
    assert hasattr(result, "_grid")
    assert result.grid() is image.grid()
    assert result.eq(2).all()

    result = image.add(1)
    assert type(result) is Image
    assert hasattr(result, "_grid")
    assert result.grid() is image.grid()
    assert result.eq(1).all()

    result = image.clone()
    assert type(result) is Image
    assert hasattr(result, "_grid")
    assert result.grid() is not image.grid()
    assert result.grid() == image.grid()
    assert result.data_ptr() != image.data_ptr()

    result = image.to("cpu", torch.int16)
    assert type(result) is Image
    assert hasattr(result, "_grid")
    assert result.grid() is image.grid()
    assert result.device == torch.device("cpu")
    assert result.dtype == torch.int16

    if torch.cuda.is_available():
        result = image.cuda()
        assert type(result) is Image
        assert hasattr(result, "_grid")
        assert result.grid() is image.grid()
        assert result.is_cuda


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_batch(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    batch = image.batch()
    assert type(batch) is ImageBatch
    assert hasattr(batch, "_grid")
    assert type(batch._grid) is tuple
    assert len(batch._grid) == 1
    assert batch.data_ptr() == image.data_ptr()


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (3,)], indirect=True)
def test_image_grid(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert image.grid() is grid

    new_grid = Grid(size=grid.size(), spacing=(0.5, 0.4, 0.3))

    new_image = image.grid(new_grid)
    assert new_image is not image
    assert image.grid() is grid
    assert new_image.grid() is new_grid
    assert new_image.data_ptr() == image.data_ptr()

    other_image = image.grid_(new_grid)
    assert other_image is image
    assert image.grid() is new_grid


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (3,)], indirect=True)
def test_image_align_corners(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert image.align_corners() == grid.align_corners()
    assert grid.align_corners() == ALIGN_CORNERS
    grid.align_corners_(not ALIGN_CORNERS)
    assert image.align_corners() == grid.align_corners()
    assert grid.align_corners() == (not ALIGN_CORNERS)


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (3,)], indirect=True)
def test_image_center(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert isinstance(image.center(), Tensor)
    assert image.center().shape == grid.center().shape
    assert image.center().shape == (grid.ndim,)
    assert torch.allclose(image.center(), grid.center())


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_origin(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert isinstance(image.origin(), Tensor)
    assert image.origin().shape == grid.origin().shape
    assert image.origin().shape == (grid.ndim,)
    assert torch.allclose(image.origin(), grid.origin())


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_spacing(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert isinstance(image.spacing(), Tensor)
    assert image.spacing().shape == grid.spacing().shape
    assert image.spacing().shape == (grid.ndim,)
    assert torch.allclose(image.spacing(), grid.spacing())


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_direction(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert isinstance(image.direction(), Tensor)
    assert image.direction().shape == grid.direction().shape
    assert image.direction().shape == (grid.ndim, grid.ndim)
    assert torch.allclose(image.direction(), grid.direction())


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_sdim(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert type(image.sdim) is int
    assert image.sdim == grid.ndim


@pytest.mark.parametrize("zeros,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_nchannels(zeros: Tensor, grid: Grid) -> None:
    image = Image(zeros, grid)
    assert type(image.nchannels) is int
    assert image.nchannels == 1


@pytest.mark.parametrize("data,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_normalize(data: Tensor, grid: Grid) -> None:
    image = Image(data, grid)
    assert image.min().lt(0)
    assert image.max().gt(1)

    result = image.normalize(mode="unit")
    assert type(result) is Image
    assert result is not image
    assert result.data_ptr() != image.data_ptr()
    assert image.eq(data).all()
    assert torch.allclose(result.min(), torch.tensor(0.0))
    assert torch.allclose(result.max(), torch.tensor(1.0))

    assert image.normalize().eq(result).all()

    result = image.normalize("center")
    assert type(result) is Image
    assert result is not image
    assert result.data_ptr() != image.data_ptr()
    assert image.eq(data).all()
    assert torch.allclose(result.min(), torch.tensor(-0.5))
    assert torch.allclose(result.max(), torch.tensor(0.5))

    result = image.normalize_("center")
    assert type(result) is Image
    assert result is not image
    assert result.data_ptr() == image.data_ptr()
    assert torch.allclose(result.min(), torch.tensor(-0.5))
    assert torch.allclose(result.max(), torch.tensor(0.5))
    assert torch.allclose(image.min(), torch.tensor(-0.5))
    assert torch.allclose(image.max(), torch.tensor(0.5))


@pytest.mark.parametrize("data,grid", [(d, d) for d in (2, 3)], indirect=True)
def test_image_rescale(data: Tensor, grid: Grid) -> None:
    image = Image(data, grid)
    input_min = image.min()
    input_max = image.max()
    assert input_min.lt(0)
    assert input_max.gt(1)

    result = image.rescale(0, 1)
    assert type(result) is Image
    assert result is not image
    assert result.data_ptr() != image.data_ptr()
    assert image.eq(data).all()
    assert torch.allclose(result.min(), torch.tensor(0.0))
    assert torch.allclose(result.max(), torch.tensor(1.0))

    assert torch.allclose(image.rescale(0, 1, input_min, input_max), result)

    result = image.rescale(-0.5, 0.5, data_max=input_max)
    assert type(result) is Image
    assert result is not image
    assert result.data_ptr() != image.data_ptr()
    assert image.eq(data).all()
    assert torch.allclose(result.min(), torch.tensor(-0.5))
    assert torch.allclose(result.max(), torch.tensor(0.5))

    result = image.rescale(0, 255, dtype=torch.uint8)
    assert type(result) is Image
    assert result is not image
    assert result.data_ptr() != image.data_ptr()
    assert result.dtype == torch.uint8
    assert result.min().eq(0)
    assert result.max().eq(255)


def test_image_sample() -> None:
    shape = torch.Size((2, 32, 64, 63))
    data: Tensor = torch.arange(shape.numel())
    data = data.reshape(shape)
    grid = Grid(shape=shape[1:])
    image = Image(data, grid)

    indices = torch.arange(0, grid.numel(), 10)
    voxels = U.unravel_coords(indices, grid.size())
    coords = grid.index_to_cube(voxels)
    assert coords.dtype == grid.dtype
    assert coords.dtype.is_floating_point
    assert coords.shape == (len(indices), grid.ndim)
    assert coords.min().ge(-1)
    assert coords.max().le(1)

    result = image.sample(coords, mode="nearest")
    expected = data.flatten(1).index_select(1, indices)
    assert type(result) is Tensor
    assert result.dtype == image.dtype
    assert result.shape == (image.nchannels, *coords.shape[:-1])
    assert result.shape == expected.shape
    assert result.eq(expected).all()

    result = image.sample(coords, mode="linear")
    assert type(result) is Tensor
    assert result.is_floating_point()
    assert result.dtype != image.dtype

    # Grid points
    coords = grid.coords()
    assert coords.ndim == image.ndim
    result = image.sample(coords, mode="nearest")
    assert type(result) is Tensor
    assert result.dtype == image.dtype
    assert result.device == image.device
    assert result.shape[0] == image.nchannels
    assert result.shape[1:] == grid.shape
    assert torch.allclose(result, image)

    # Batch of grid points
    coords = grid.coords()
    coords = coords.unsqueeze(0).repeat((3,) + (1,) * coords.ndim)
    assert coords.ndim == image.ndim + 1
    result = image.sample(coords, mode="nearest")
    assert type(result) is Tensor
    assert result.dtype == image.dtype
    assert result.device == image.device
    assert result.shape[0] == image.nchannels
    assert result.shape[1] == coords.shape[0]
    assert result.shape[2:] == grid.shape

    batch_result = image.batch().sample(coords, mode="nearest")
    assert type(result) is Tensor
    assert batch_result.dtype == image.dtype
    assert batch_result.device == image.device
    assert batch_result.shape[0] == coords.shape[0]
    assert batch_result.shape[1] == image.nchannels
    assert batch_result.shape[2:] == grid.shape
    assert torch.allclose(result, batch_result.transpose(0, 1))

    # Sampling grid
    result = image.sample(grid)
    assert type(result) is Image
    assert result.grid() is grid
    assert result.data_ptr() == image.data_ptr()
    assert result is image

    shape = torch.Size((3, 31, 63, 63))
    data: Tensor = torch.arange(shape.numel())
    data = data.reshape(shape)
    grid = Grid(shape=shape[1:])
    image = Image(data, grid)

    ds_grid = grid.downsample()
    ds_image = image.sample(ds_grid)
    assert type(ds_image) is Image
    assert ds_image.grid() is ds_grid
    assert ds_image.nchannels == image.nchannels
    assert ds_image.device == image.device
    assert ds_image.is_floating_point()

    indices = torch.arange(0, grid.numel())
    voxels = U.unravel_coords(indices, grid.size())
    coords = grid.index_to_cube(voxels)
    coords = coords.reshape(grid.shape + (grid.ndim,))
    coords = coords[::2, ::2, ::2, :]
    assert torch.allclose(coords, ds_grid.coords())

    result = image.sample(coords)
    assert result.is_floating_point()
    assert torch.allclose(ds_image, result)