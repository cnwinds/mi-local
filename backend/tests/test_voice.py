from homehub.voice import cn_number, parse

DEVICES = {"midea.1": "书房空调"}


def test_cn_number():
    assert cn_number("26") == 26
    assert cn_number("二十六") == 26
    assert cn_number("十八") == 18
    assert cn_number("三十") == 30
    assert cn_number("abc") is None


def test_power():
    assert parse("打开书房空调", DEVICES) == ("midea.1", [("turn_on", None)], "好的，书房空调已打开")
    assert parse("把书房的空调关了", DEVICES)[1] == [("turn_off", None)]
    assert parse("关闭书房空调", DEVICES)[1] == [("turn_off", None)]


def test_temperature_and_mode():
    _, actions, reply = parse("书房空调调到二十六度", DEVICES)
    assert actions == [("set_temp", 26.0)]
    assert reply == "好的，书房空调26度"
    _, actions, _ = parse("打开书房空调制冷", DEVICES)
    assert actions == [("turn_on", None), ("set_mode", "cool")]
    assert parse("书房空调调高一点", DEVICES)[1] == [("temp_delta", 1)]


def test_unrelated_queries_are_ignored():
    assert parse("打开卧室空调", DEVICES) is None
    assert parse("今天天气怎么样", DEVICES) is None
    assert parse("书房空调", DEVICES) is None
