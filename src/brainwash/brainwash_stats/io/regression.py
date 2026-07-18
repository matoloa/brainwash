"""Legacy IO regression entry — delegates to textbook IO ANCOVA (PR-C)."""

from .ancova import compute_io_ancova


def _compute_io_regression_internal(
    shown_groups,
    get_group_testset_means_fn,
    uistate=None,
    n_unit="subject",
    norm=False,
    amp=True,
    slope=True,
    dd_groups=None,
    **kwargs,
):
    return compute_io_ancova(
        shown_groups,
        get_group_testset_means_fn,
        uistate=uistate,
        n_unit=n_unit,
        norm=norm,
        amp=amp,
        slope=slope,
        dd_groups=dd_groups,
        **kwargs,
    )
