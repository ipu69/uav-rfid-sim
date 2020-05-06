from math import sin, cos, pi

from pysim.utils import random_hex_string
from pysim import simulate


# noinspection PyPep8Naming
def test_reading_tags_in_circle_with_zero_ber():
    """Test reader flying above tags via a circle trajectory with ideal channel.

    Six tags are placed in a circle at equal distances from each other.
    Circle has radius R = 10 meters. Channel is ideal, meaning that BER = 0
    when distance between the reader and the tag is less than D meters
    (assume D = 2 meters). Reader is flying above tags at altitude H = 1 meter,
    so when it is above one tag, only it can be read.

    Since the channel is ideal and distances are large enough, we can be sure
    that no collisions or reply loss due to high BER may occur, and each tag
    will be read as soon as the reader arrives above the tag, if its velocity
    is not too large (at least one inventory round takes place).

    :return:
    """
    R = 10    # circle radius
    H = 1.0   # reader altitude
    V = 4.0   # meters per second, reader velocity
    D = 2.0   # meters, channel distance

    spec = {
        'mobility': {
            'update_timeout': 0.1,
        },
        'reader': {
            'position': (R, 0, H),
            'Q': 2,
            'M': 1,
            'DR': '8',
            'trext': False,
            'sel': 'ALL',
            'tari': 6.25e-6,
            'rtcal': 15.0e-6,
            'trcal': 20.0e-6,
            'session': 0,
            'target': 'A',
            'trajectory': {
                'center': (0, 0, 0),
                'angle0': 0,
                'point_area_radius': D * 1.01,
                'radius': R,
                'velocity': V,  # meters per second
                'altitude': H,  # meter
            },
            'stats': {
                'record_read_timestamps': False,
            }
        },
        'tags': [{
            'id': i,
            'sensitivity': -20.0,  # dBm
            'position': (cos(pi/3 * i) * R, sin(pi/3 * i) * R, 0),
            'epcid': random_hex_string(24),
            'switch_target': True,
        } for i in range(6)],
        'channel': {
            'model': 'models.channels.ConstantChannel',
            'distance': D,
            'ber': 0,
        },
        'propagation': {
            'model': 'models.propagation.NoLossPropagationModel',
            'distance': D,
        }
    }

    # I define max simulation time as the time, needed to fly above each tag
    # twice, i.e. (2 - 1/12 - 0.0001) *pi*R / V. Subtracting 0.0001 is needed
    # to prohibit third attempt to connect to the first tag.
    sim_time_limit = (4 - 1/12 - 0.0001) * pi * R / V

    # Running the simulation:
    ret = simulate(spec, sim_time_limit=sim_time_limit)
    # print(ret)

    # 1) Check that each tag was read exactly two times
    for i in range(6):
        assert ret['tags'][i]['read_count'] == 2

    # 2) Check that no collisions appeared
    for i in range(6):
        assert ret['c1g2_stats']['num_collisions'] == 0

    # 3) Check that there were exactly 2 trajectory passes
    assert len(ret['routes']) == 2

    # TODO: add more inspections here
