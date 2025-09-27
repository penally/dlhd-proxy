from dlhd_proxy.step_daddy import Channel, StepDaddy


def test_enumerate_duplicate_names():
    channels = [
        Channel(id="1", name="MLB League Pass", tags=[], logo="logo1"),
        Channel(id="2", name="MLB League Pass", tags=[], logo="logo2"),
        Channel(id="3", name="Other", tags=[], logo="logo3"),
        Channel(id="4", name="MLB League Pass", tags=[], logo="logo4"),
    ]

    StepDaddy._enumerate_duplicate_names(channels)

    assert [channel.name for channel in channels] == [
        "MLB League Pass (1)",
        "MLB League Pass (2)",
        "Other",
        "MLB League Pass (3)",
    ]
