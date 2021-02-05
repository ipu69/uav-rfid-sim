from model.des.cyscheduler import CyScheduler
from model.des.pyscheduler import PyScheduler

from model.des.pyscheduler import SpecType
from model.handlers import events as ev, handlers as eh
from model.objects.scene import Scene, SceneSpec

SCHEDULER_CLASS = CyScheduler


# noinspection DuplicatedCode
def simulate_single_pass(parameters: SceneSpec, scheduler_class=SCHEDULER_CLASS):
    """Simulates single pass of UAV-Reader over a sensor.
    """
    scheduler = scheduler_class()

    # Create the scene:
    #    - create and put the reader (with +- random position offset)
    #    - create and put the tag
    scene = Scene(parameters)
    scheduler.setup_context(scene, parameters)

    # Setup initialization:
    scheduler.bind_init(eh.initialize)

    # Setup events handlers:
    scheduler.bind(ev.READER_LEFT, eh.reader_left)
    scheduler.bind(ev.UPDATE_POSITIONS, eh.update_positions)
    scheduler.bind(ev.START_ROUND, eh.reader_start_round)
    scheduler.bind(ev.READER_TX_END, eh.reader_tx_end)
    scheduler.bind(ev.READER_RX_START, eh.reader_rx_start, SpecType.OBJECT)
    scheduler.bind(ev.READER_RX_END, eh.reader_rx_end)
    scheduler.bind(ev.SEND_COMMAND, eh.send_command, SpecType.OBJECT)
    scheduler.bind(ev.READER_ABORT_RX, eh.reader_abort_rx)
    scheduler.bind(ev.READER_NO_REPLY, eh.no_reply)
    scheduler.bind(ev.SEND_REPLY, eh.send_reply, SpecType.OBJECT)
    scheduler.bind(ev.TAG_TX_END, eh.tag_tx_end)
    scheduler.bind(ev.TAG_RX_START, eh.tag_rx_start, SpecType.OBJECT)
    scheduler.bind(ev.TAG_RX_END, eh.tag_rx_end)
    scheduler.bind(ev.TAG_POWER_ON, eh.tag_power_on)
    scheduler.bind(ev.TAG_POWER_OFF, eh.tag_power_off)

    # Run:
    scheduler.run()  # TODO: pass max_time here!

    return scheduler.time, scene


def simulate(parameters, num_passes=10, scheduler_class=SCHEDULER_CLASS):
    """Recursively simulates a number of passes UAV-Reader over sensors.
    """
    result = []
    for _ in range(num_passes):
        ret = simulate_single_pass(parameters)
        result.append(ret)
    return result
