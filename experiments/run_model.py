from model.objects.channel import ConstChannelSpec
from model.objects.scene import SceneSpec, ReaderSpec, TagSpec
from model.simulation import simulate_single_pass

if __name__ == '__main__':
    spec = SceneSpec(
        reader=ReaderSpec(position=(-5, 0, 0)),
        tag=TagSpec(),
        channel=ConstChannelSpec(connection_distance=10.5),
        max_distance=11.0,
        position_update_interval=0.1,
        max_num_rounds=1,
        verbose=True
    )
    t, scene = simulate_single_pass(spec)
    print(scene.reader.num_rounds)
    print(scene.tag.num_epcid_sent, scene.tag.num_epcid_received)
    print(scene.tag.num_data_sent, scene.tag.num_data_received)
    print(scene.channel.distance_map)
    print(scene.channel.tag_rx_power_map)
    print(scene.channel.tag_tx_power_map)
