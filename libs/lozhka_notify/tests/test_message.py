from lozhka_notify import Message


def test_message_is_immutable_value():
    m = Message(topic="pipeline_alert", body="dbt failed")
    assert m.dedupe_key is None
    assert m == Message(topic="pipeline_alert", body="dbt failed")
