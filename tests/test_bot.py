from parkpulse.bot import detect_language, handle_message, match_zone


def test_language_detection():
    assert detect_language("parking near bahu plaza") == "en"
    assert detect_language("रघुनाथ बाजार के पास पार्किंग") == "hi"
    assert detect_language("रघुनाथ बजार दे कोल पार्किंग कुत्थें ऐ") == "doi"
    assert detect_language("بس اسٹینڈ کے قریب پارکنگ") == "ur"


def test_zone_matching_handles_typos_and_scripts():
    assert match_zone("parking near raghunath bazar").id == "raghunath-bazaar"
    assert match_zone("गांधी नगर").id == "gandhi-nagar"
    assert match_zone("ریلوے اسٹیشن").id == "railway-station"
    assert match_zone("somewhere unknown") is None


def test_find_then_reply_number_for_directions(state):
    sess = {}
    r = handle_message(state, "parking near bahu plaza", session=sess)
    assert r.intent == "find" and len(r.data["options"]) >= 1
    d = handle_message(state, "1", session=sess)
    assert d.intent == "directions" and "google.com/maps" in d.text


def test_location_pin_and_report(state):
    assert handle_message(state, location=(32.728, 74.862)).intent == "find"
    r = handle_message(state, "report car blocking city chowk")
    assert r.intent == "report" and r.data["zone_id"] == "residency-road"
