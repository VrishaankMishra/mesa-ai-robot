"""Tests for the two-site figure script's pure aggregation helpers."""

import importlib.util
import math
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "eval_site_figures", Path(__file__).resolve().parent.parent / "scripts" / "eval_site_figures.py"
)
esf = importlib.util.module_from_spec(spec)
sys.modules["eval_site_figures"] = esf
spec.loader.exec_module(esf)

HEADER_OLD = "model,condition,session,scene,ground_truth,mark_m,frame,correct,gt_confidence\n"
HEADER_NEW = "model,site,condition,session,scene,ground_truth,mark_m,frame,correct,gt_confidence\n"


def _row_old(model, cond, med, mark, correct, scene="single"):
    return f"{model},{cond},s1,{scene},{med},{mark},f.jpg,{correct},0.5\n"


def _row_new(model, site, cond, med, mark, correct, scene="single"):
    return f"{model},{site},{cond},s2,{scene},{med},{mark},f.jpg,{correct},0.5\n"


def _two_site_csvs(tmp_path):
    """Site A: advil 3/4 at midday (2/2 near, 1/2 far). Site B: advil 1/4 (1/2, 0/2).
    Extra rows that must be ignored: a probe scene, the afternoon pair, a pilot, arm v1."""
    a = tmp_path / "a.csv"
    a.write_text(HEADER_OLD + "".join([
        _row_old("best", "midday_lamps_off", "advil", "0.6", 1),
        _row_old("best", "midday_lamps_off", "advil", "0.6", 1),
        _row_old("best", "midday_lamps_off", "advil", "0.8", 1),
        _row_old("best", "midday_lamps_off", "advil", "0.8", 0),
        _row_old("best", "midday_lamp_added", "advil", "0.6", 1),
        _row_old("best", "midday_lamp_added", "advil", "0.8", 1),
        _row_old("best", "midday_lamps_off", "benadryl", "0.6", 1, scene="unknown"),
        _row_old("best_v1_backup", "midday_lamps_off", "advil", "0.6", 0),
    ]))
    b = tmp_path / "b.csv"
    b.write_text(HEADER_NEW + "".join([
        _row_new("best", "family_room", "midday_lamps_off", "advil", "0.6", 1),
        _row_new("best", "family_room", "midday_lamps_off", "advil", "0.6", 0),
        _row_new("best", "family_room", "midday_lamps_off", "advil", "0.8", 0),
        _row_new("best", "family_room", "midday_lamps_off", "advil", "0.8", 0),
        _row_new("best", "family_room", "midday_lamp_added", "advil", "0.6", 0),
        _row_new("best", "family_room", "midday_lamp_added", "advil", "0.8", 0),
        _row_new("best", "family_room", "afternoon_blinds_dim", "advil", "0.6", 1),
        _row_new("best", "family_room", "afternoon_blinds_dim_lamp", "advil", "0.6", 1),
        _row_new("best", "family_room", "midday_lamps_off_pilot_steep_manualexp", "advil", "0.6", 1),
        _row_new("best_v3syn", "family_room", "midday_lamps_off", "advil", "0.6", 1),
    ]))
    return [a, b]


class TestGridFilter:
    def test_shared_conditions_pass(self):
        assert all(esf.is_grid_condition(c) for c in esf.SHARED_CONDITIONS)

    def test_afternoon_pair_and_pilot_are_skipped(self):
        assert not esf.is_grid_condition("afternoon_blinds_dim")
        assert not esf.is_grid_condition("afternoon_blinds_dim_lamp")
        assert not esf.is_grid_condition("midday_lamps_off_pilot_steep_manualexp")


class TestLoadCells:
    def test_siteless_rows_default_and_non_grid_rows_dropped(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        sites = {s for s, _, _, _, _ in cells}
        assert sites == {"home_office", "family_room"}
        conds = {c for _, _, c, _, _ in cells}
        assert conds == {"midday_lamps_off", "midday_lamp_added"}
        # the unknown probe row never enters single-scene cells
        assert ("home_office", "best", "midday_lamps_off", "benadryl", "0.6") not in cells

    def test_counts_pool_over_marks_and_filter_by_mark(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        assert esf.counts(cells, "home_office", "best", "midday_lamps_off", "advil") == (3, 4)
        assert esf.counts(cells, "home_office", "best", "midday_lamps_off", "advil", "0.8") == (1, 2)
        assert esf.counts(cells, "family_room", "best", "midday_lamps_off") == (1, 4)
        assert esf.counts(cells, "family_room", "best", "evening_dim") == (0, 0)

    def test_arms_keep_fixed_order(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        assert esf.arms_in(cells, "home_office") == ["best", "best_v1_backup"]
        assert esf.arms_in(cells, "family_room") == ["best", "best_v3syn"]


class TestMatrices:
    def test_rate_matrix_shape_and_values(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        m = esf.rate_matrix(cells, "home_office", conds=["midday_lamps_off"], meds=["advil", "mylanta"])
        assert m[0][0] == 0.75 and math.isnan(m[0][1])

    def test_delta_matrix_sign_and_flag(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        d = esf.delta_matrix(cells, "family_room", "home_office",
                             conds=["midday_lamps_off", "midday_lamp_added"], meds=["advil"])
        assert math.isclose(d[0][0][0], 0.25 - 0.75)
        assert d[0][0][1] is False              # 4 vs 4 frames: interval straddles zero
        assert math.isclose(d[1][0][0], -1.0)   # 0/2 vs 2/2
        # a missing cell is (nan, False)
        d2 = esf.delta_matrix(cells, "family_room", "home_office", conds=["evening_dim"], meds=["advil"])
        assert math.isnan(d2[0][0][0]) and d2[0][0][1] is False

    def test_delta_flag_matches_newcombe_on_real_sized_cells(self):
        cells = {("ref", "best", "evening_dim", "advil", "0.6"): [9, 22],
                 ("new", "best", "evening_dim", "advil", "0.6"): [22, 22]}
        (d, flag), = esf.delta_matrix(cells, "new", "ref", conds=["evening_dim"], meds=["advil"])[0]
        assert math.isclose(d, 13 / 22) and flag is True


class TestPooledStatistics:
    def test_pooled_ci_is_wilson(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        r, lo, hi, k, n = esf.pooled_ci(cells, "home_office", "best", "midday_lamps_off")
        assert (k, n) == (3, 4) and r == 0.75
        assert (lo, hi) == esf.wilson_ci(3, 4)

    def test_lamp_lift_is_newcombe_on_minus_off(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        d, lo, hi = esf.lamp_lift(cells, "home_office", "midday_lamps_off", "midday_lamp_added")
        assert (d, lo, hi) == esf.newcombe_diff_ci(2, 2, 3, 4)
        assert math.isclose(d, 0.25)

    def test_cross_site_delta_at_far_mark(self, tmp_path):
        cells = esf.load_cells(_two_site_csvs(tmp_path))
        d, lo, hi = esf.cross_site_delta(cells, "family_room", "home_office", "midday_lamps_off", mark="0.8")
        assert (d, lo, hi) == esf.newcombe_diff_ci(0, 2, 1, 2)
        assert math.isclose(d, -0.5)

    def test_missing_cells_are_nan(self):
        assert all(math.isnan(v) for v in esf.lamp_lift({}, "x", "a", "b"))
        assert math.isnan(esf.pooled_ci({}, "x", "best", "a")[0])
