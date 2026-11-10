import os

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from homehub.camera_events import decrypt, kind_of, parse_playlist
from homehub.ranges import byte_range

PLAYLIST = """#EXTM3U
#EXT-X-VERSION:7
#EXT-X-KEY:METHOD=AES-128,URI="https://app.processor.smartcamera.api.io.mi.com/common/app/play/v1/key?did=1&keyInfo=x",IV=0x7F169F6616F2E0DD132773E188915219
#EXTINF:2.601
https://app.processor.smartcamera.api.io.mi.com/common/app/play/v1/video?did=1&stoId=a
#EXT-X-DISCONTINUITY
#EXTINF:8.5
https://app.processor.smartcamera.api.io.mi.com/common/app/play/v1/video?did=1&stoId=b
#EXT-X-ENDLIST
"""


def test_most_specific_detector_wins():
    assert kind_of("ObjectMotion:PeopleMotion") == "person"
    assert kind_of("ObjectMotion") == "motion"
    assert kind_of("Something") == "other"


def test_decrypt_strips_padding():
    key, iv, clip = os.urandom(16), os.urandom(16), b"\x00\x00\x00\x20ftypisom" + os.urandom(37)
    sealed = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(clip, 16))
    assert decrypt(sealed, key, iv) == clip


def test_parse_playlist():
    playlist = parse_playlist(PLAYLIST)
    assert playlist["iv"].hex() == "7f169f6616f2e0dd132773e188915219"
    assert [s.rsplit("=", 1)[1] for s in playlist["segments"]] == ["a", "b"]
    assert playlist["durations"] == [2.601, 8.5]
    assert playlist["key_url"].endswith("keyInfo=x")


def test_byte_ranges():
    assert byte_range("", 1000) is None
    assert byte_range("bytes=0-1", 1000) == (0, 1)
    assert byte_range("bytes=500-", 1000) == (500, 999)
    assert byte_range("bytes=-10", 1000) == (990, 999)
    assert byte_range("bytes=0-5000", 1000) == (0, 999)
    with pytest.raises(ValueError):
        byte_range("bytes=2000-", 1000)
