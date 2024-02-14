def test_path_extraction():
    import pymotility.path_extraction as pe
    from skvideo.io import vread
    import os
    from datetime import datetime
    import matplotlib.pyplot as plt
    import numpy as np

    root = "tests/data/simple_video"
    vid_names = [
        f"{root}/{name}" for name in os.listdir(root) if name.endswith(".mp4")
    ]
    current = datetime.now().strftime("%d-%m-%y_%H:%M:%S")
    output_dir = f"tests/data/path_extraction/{current}"
    os.mkdir(output_dir)
    videos = [vread(vid_name) for vid_name in vid_names]
    for method in pe.methods:
        os.mkdir(f"{output_dir}/{method}")
        paths = pe.extract_path(videos, method=method, denoise=False)
        for i, vid_name in enumerate(vid_names):
            name = vid_name.split("/")[-1].split(".")[0]
            np.save(f"{output_dir}/{method}/{name}.npy", paths[i])
            fig, ax = pe.plot_frame(-1, videos[i], paths[i])
            plt.savefig(f"{output_dir}/{method}/{name}.png")


if __name__ == "__main__":
    test_path_extraction()