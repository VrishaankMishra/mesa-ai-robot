"""Tests for the statistics pass (Wilson, Newcombe, trend, sign test, site aggregation)."""

import importlib.util
import math
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "eval_stats", Path(__file__).resolve().parent.parent / "scripts" / "eval_stats.py"
)
es = importlib.util.module_from_spec(spec)
sys.modules["eval_stats"] = es
spec.loader.exec_module(es)


class TestWilson:
    def test_half_of_100(self):
        lo, hi = es.wilson_ci(50, 100)
        assert math.isclose(lo, 0.4038, abs_tol=5e-4)
        assert math.isclose(hi, 0.5962, abs_tol=5e-4)

    def test_zero_hits_has_zero_lower_bound_and_nonzero_upper(self):
        lo, hi = es.wilson_ci(0, 22)
        assert lo == 0.0
        assert 0.1 < hi < 0.2  # ~0.149: a 0/22 cell is not "certainly zero"

    def test_all_hits_upper_is_one(self):
        lo, hi = es.wilson_ci(22, 22)
        assert hi == 1.0
        assert 0.8 < lo < 0.9

    def test_empty_cell_is_nan(self):
        lo, hi = es.wilson_ci(0, 0)
        assert math.isnan(lo) and math.isnan(hi)


class TestNewcombe:
    def test_sign_and_symmetry(self):
        d, lo, hi = es.newcombe_diff_ci(20, 22, 10, 22)
        assert math.isclose(d, 10 / 22)
        assert lo < d < hi
        d2, lo2, hi2 = es.newcombe_diff_ci(10, 22, 20, 22)
        assert math.isclose(d2, -d) and math.isclose(lo2, -hi) and math.isclose(hi2, -lo)

    def test_identical_cells_interval_straddles_zero(self):
        d, lo, hi = es.newcombe_diff_ci(15, 22, 15, 22)
        assert d == 0 and lo < 0 < hi

    def test_clear_lift_excludes_zero(self):
        _, lo, _ = es.newcombe_diff_ci(22, 22, 9, 22)  # advil 41 -> 100
        assert lo > 0


class TestTrend:
    def test_perfect_increasing_trend(self):
        z, p = es.cochran_armitage([(2, 22, 30), (10, 22, 60), (18, 22, 90), (22, 22, 120)])
        assert z > 3 and p < 0.01

    def test_decreasing_trend_is_negative(self):
        z, _ = es.cochran_armitage([(22, 22, 30), (10, 22, 60), (2, 22, 90)])
        assert z < 0

    def test_flat_profile_is_null(self):
        z, p = es.cochran_armitage([(11, 22, 30), (11, 22, 60), (11, 22, 90)])
        assert abs(z) < 1e-9 and math.isclose(p, 1.0)

    def test_two_sided_collapse_has_weak_linear_trend(self):
        # High in the middle, low at both ends: the paper's shape. Linear z near zero.
        z, _ = es.cochran_armitage([(5, 22, 30), (21, 22, 60), (21, 22, 90), (5, 22, 120)])
        assert abs(z) < 1.0

    def test_degenerate_inputs_are_nan(self):
        assert all(math.isnan(v) for v in es.cochran_armitage([(5, 22, 30)]))
        assert all(math.isnan(v) for v in es.cochran_armitage([(5, 22, 30), (9, 22, 30)]))
        assert all(math.isnan(v) for v in es.cochran_armitage([(22, 22, 30), (22, 22, 60)]))


class TestSignTest:
    def test_all_up_eight_meds(self):
        pos, neg, ties, p = es.sign_test([0.1] * 8)
        assert (pos, neg, ties) == (8, 0, 0)
        assert math.isclose(p, 2 / 256)

    def test_ties_are_dropped(self):
        pos, neg, ties, p = es.sign_test([0.2, -0.1, 0.0, 0.0])
        assert (pos, neg, ties) == (1, 1, 2)
        assert math.isclose(p, 1.0)

    def test_no_information_is_nan(self):
        assert math.isnan(es.sign_test([0.0, 0.0])[3])


class TestSpearman:
    def test_identity_and_reversal(self):
        xs = [0.3, 0.9, 0.5, 0.1, 0.7]
        assert math.isclose(es.spearman(xs, xs), 1.0)
        assert math.isclose(es.spearman(xs, [-x for x in xs]), -1.0)

    def test_ties_get_average_ranks(self):
        assert es._ranks([1.0, 1.0, 2.0]) == [1.5, 1.5, 3.0]

    def test_too_short_is_nan(self):
        assert math.isnan(es.spearman([1.0, 2.0], [1.0, 2.0]))


HEADER_OLD = "model,condition,session,scene,ground_truth,mark_m,frame,correct,gt_confidence\n"
HEADER_NEW = "model,site,condition,session,scene,ground_truth,mark_m,frame,correct,gt_confidence\n"


def _write(path, header, rows):
    path.write_text(header + "".join(rows))


class TestLoadResults:
    def test_siteless_rows_belong_to_reference_and_other_models_are_skipped(self, tmp_path):
        csv_a = tmp_path / "a.csv"
        _write(csv_a, HEADER_OLD, [
            "best,evening_dim,s1,single,advil,0.6,f01.jpg,1,0.7\n",
            "best,evening_dim,s1,single,advil,0.6,f02.jpg,0,0.2\n",
            "best_v1_backup,evening_dim,s1,single,advil,0.6,f01.jpg,1,0.7\n",
        ])
        cells = es.load_results([csv_a], "best", "home_office")
        assert cells[("home_office", "evening_dim", "single", "advil")] == [1, 2]
        assert len(cells) == 1

    def test_two_csvs_two_sites_merge(self, tmp_path):
        csv_a, csv_b = tmp_path / "a.csv", tmp_path / "b.csv"
        _write(csv_a, HEADER_OLD, ["best,evening_dim,s1,single,advil,0.6,f01.jpg,1,0.7\n"])
        _write(csv_b, HEADER_NEW, [
            "best,living_room,evening_dim,s2,single,advil,0.6,f01.jpg,0,0.1\n",
            "best,living_room,evening_dim,s2,unknown,benadryl,0.6,f01.jpg,1,\n",
        ])
        cells = es.load_results([csv_a, csv_b], "best")
        assert es.sites_in(cells) == ["home_office", "living_room"]
        assert es.pooled_single(cells, "living_room", "evening_dim") == (0, 1)
        assert es.probe(cells, "living_room", "evening_dim") == (1, 1)

    def test_report_builds_with_reference_and_replication(self, tmp_path):
        csv_a, csv_b = tmp_path / "a.csv", tmp_path / "b.csv"
        rows_a, rows_b = [], []
        for cond in ("evening_dim", "evening_dim_lamp"):
            for i in range(4):
                rows_a.append(f"best,{cond},s1,single,advil,0.6,f{i:02d}.jpg,{int(i < 2)},0.5\n")
                rows_b.append(f"best,living_room,{cond},s2,single,advil,0.6,f{i:02d}.jpg,1,0.9\n")
        _write(csv_a, HEADER_OLD, rows_a)
        _write(csv_b, HEADER_NEW, rows_b)
        cells = es.load_results([csv_a, csv_b], "best")
        lum = {("home_office", "evening_dim"): {"gray": 30.0, "blown": 0.1},
               ("home_office", "evening_dim_lamp"): {"gray": 60.0, "blown": 0.0}}
        report = es.build_report(cells, "best", "home_office", lum, ["a.csv", "b.csv"])
        assert "## Site `home_office`" in report
        assert "## Site `living_room`" in report
        assert "## Replication: `living_room` vs `home_office`" in report
        assert "Cochran–Armitage" in report          # luminance present for the reference
        assert "No scene luminance" in report        # and absent for the new site


def test_load_luminance_averages_sessions(tmp_path):
    lum = tmp_path / "lum.csv"
    lum.write_text("site,condition,session,median_gray,blown_pct,dark_pct,source\n"
                   ",evening_dim,s1,30,0,5,retro_frame00\n"
                   ",evening_dim,s2,50,0,5,retro_frame00\n"
                   "living_room,evening_dim,s3,70,0,1,capture_start\n")
    got = es.load_luminance(lum, "home_office")
    assert got[("home_office", "evening_dim")] == {"gray": 40.0, "blown": 0.0}
    assert got[("living_room", "evening_dim")]["gray"] == 70.0
