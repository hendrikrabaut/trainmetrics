import struct
from datetime import datetime, timezone

import pytest

from app.services.importers import ActivityFileError, parse_activity_file


FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc).timestamp()
START = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _fit_crc(data: bytes) -> int:
    table = [
        0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
        0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
    ]
    crc = 0

    for byte in data:
        for nibble in (byte & 0xF, byte >> 4):
            shifted = table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ shifted ^ table[nibble]

    return crc


def _fit_file(sessions: list[tuple[int, int, int]]) -> bytes:
    """Builds a FIT file from (sport, timer_ms, distance_cm) sessions."""
    fields = [
        (2, 4, 0x86),   # start_time
        (5, 1, 0x00),   # sport
        (8, 4, 0x86),   # total_timer_time, ms
        (9, 4, 0x86),   # total_distance, cm
        (14, 2, 0x84),  # avg_speed, mm/s
        (16, 1, 0x02),  # avg_heart_rate
        (17, 1, 0x02),  # max_heart_rate
        (22, 2, 0x84),  # total_ascent
        (11, 2, 0x84),  # total_calories
    ]

    body = struct.pack("<BBBHB", 0x40, 0, 0, 18, len(fields))

    for number, size, base_type in fields:
        body += struct.pack("<BBB", number, size, base_type)

    start = int(START.timestamp() - FIT_EPOCH)

    for sport, timer, distance in sessions:
        body += struct.pack(
            "<BIBIIHBBHH",
            0x00, start, sport, timer, distance, 3080, 150, 175, 42, 700,
        )

    header = struct.pack("<BBHI4s", 14, 0x20, 2100, len(body), b".FIT")
    header += struct.pack("<H", _fit_crc(header))
    file = header + body

    return file + struct.pack("<H", _fit_crc(file))


GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk><name>Morning</name><type>running</type><trkseg>
    <trkpt lat="51.0000" lon="4.0000"><ele>10</ele><time>2026-09-29T12:00:00Z</time>
      <extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>140</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>
    </trkpt>
    <trkpt lat="51.0100" lon="4.0000"><ele>30</ele><time>2026-09-29T12:06:00Z</time>
      <extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>160</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>
    </trkpt>
  </trkseg></trk>
</gpx>"""


TCX = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Biking">
    <Id>2026-09-29T12:00:00.000Z</Id>
    <Lap StartTime="2026-09-29T12:00:00.000Z">
      <TotalTimeSeconds>1000</TotalTimeSeconds><DistanceMeters>8000</DistanceMeters>
      <Calories>200</Calories>
      <AverageHeartRateBpm><Value>120</Value></AverageHeartRateBpm>
      <MaximumHeartRateBpm><Value>140</Value></MaximumHeartRateBpm>
      <Track>
        <Trackpoint><AltitudeMeters>10</AltitudeMeters></Trackpoint>
        <Trackpoint><AltitudeMeters>25</AltitudeMeters></Trackpoint>
        <Trackpoint><AltitudeMeters>20</AltitudeMeters></Trackpoint>
      </Track>
    </Lap>
    <Lap StartTime="2026-09-29T12:16:40.000Z">
      <TotalTimeSeconds>3000</TotalTimeSeconds><DistanceMeters>24000</DistanceMeters>
      <Calories>600</Calories>
      <AverageHeartRateBpm><Value>160</Value></AverageHeartRateBpm>
      <MaximumHeartRateBpm><Value>180</Value></MaximumHeartRateBpm>
    </Lap>
  </Activity></Activities>
</TrainingCenterDatabase>"""


def test_fit_session_is_normalized():
    activity = parse_activity_file(
        "run.FIT",
        _fit_file([(1, 3448000, 1061000)]),
    )[0]

    assert activity.activity_type == "RUNNING"
    assert activity.date.startswith("2026-09-29T")
    assert activity.duration == 3448
    assert activity.distance == pytest.approx(10610)
    assert activity.average_speed == 3.08
    assert activity.average_heart_rate == 150
    assert activity.max_heart_rate == 175
    assert activity.elevation_gain == 42
    assert activity.calories == 700


def test_fit_triathlon_gives_one_activity_per_discipline():
    activities = parse_activity_file(
        "race.fit",
        _fit_file([
            (5, 1800000, 150000),
            (3, 120000, 0),
            (2, 4000000, 4000000),
            (1, 2700000, 1000000),
        ]),
    )

    assert [activity.activity_type for activity in activities] == [
        "SWIMMING",
        "CYCLING",
        "RUNNING",
    ]


def test_gpx_track():
    activity = parse_activity_file("run.gpx", GPX)[0]

    assert activity.activity_type == "RUNNING"
    assert activity.duration == 360
    assert 1100 < activity.distance < 1120
    assert activity.average_speed == pytest.approx(activity.distance / 360, abs=0.01)
    assert activity.average_heart_rate == 150
    assert activity.max_heart_rate == 160
    assert activity.elevation_gain > 0


def test_tcx_laps_are_combined():
    activity = parse_activity_file("ride.tcx", TCX)[0]

    assert activity.activity_type == "CYCLING"
    assert activity.duration == 4000
    assert activity.distance == 32000
    assert activity.average_speed == 8
    assert activity.average_heart_rate == 150
    assert activity.max_heart_rate == 180
    assert activity.elevation_gain == 15
    assert activity.calories == 800


@pytest.mark.parametrize(
    "filename, content",
    [
        ("notes.txt", b"hello"),
        ("broken.fit", b"not a fit file"),
        ("broken.gpx", b"<gpx"),
        ("broken.tcx", b"<nope"),
        ("empty.tcx", b"<TrainingCenterDatabase/>"),
    ],
)
def test_unreadable_files_are_refused(filename, content):
    with pytest.raises(ActivityFileError):
        parse_activity_file(filename, content)


def test_upload_skips_a_file_it_already_imported(client):
    files = {"file": ("ride.tcx", TCX)}

    first = client.post("/api/import/", files=files)
    assert first.status_code == 200, first.text
    assert len(first.json()["imported"]) == 1
    assert first.json()["skipped"] == 0

    second = client.post("/api/import/", files=files).json()
    assert second["imported"] == []
    assert second["skipped"] == 1

    assert len(client.get("/api/workouts/").json()) == 1


def test_upload_of_an_unreadable_file_is_refused(client):
    response = client.post("/api/import/", files={"file": ("x.fit", b"nope")})
    assert response.status_code == 422
