from app.graph import factory_graph


def test_validate_routes_back_to_implement_on_failure():
    state = {"validation_passed": False}
    assert factory_graph._after_validate(state) == "implement"


def test_validate_routes_to_end_on_success():
    state = {"validation_passed": True}
    assert factory_graph._after_validate(state) == "end"
