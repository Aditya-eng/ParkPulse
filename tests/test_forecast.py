def test_forecast_shape_and_quality(state):
    f = state.forecast("raghunath-bazaar", hours=6)
    assert len(f["points"]) == 6
    assert all(0 <= p["occupancy"] <= 1 for p in f["points"])
    assert f["model_mae"] is not None and f["model_mae"] < 0.15
