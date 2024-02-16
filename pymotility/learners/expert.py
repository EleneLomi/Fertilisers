from preprocessing import *
import numpy as np
from tslearn.metrics import dtw
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform
from sklearn_extra.cluster import KMedoids
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import pairwise_distances
from scipy.stats import mode
import numpy as np
import os
import matplotlib.pyplot as plt
from itertools import product, permutations
import numpy as np


class MixtureOfExperts:
    def __init__(self, data, debug=False, num_clusters=3):
        self.data = data
        self.debug = debug
        self.preprocess(debug)
        self.initialize_models(num_clusters)

    def preprocess(self, debug):
        # Assuming segment_paths, recenter_paths, rotate_paths, and set_final_point_on_x_axis_path are defined
        data_processed = segment_paths(self.data)
        self.length_paths = len(data_processed[0])
        data_processed = recenter_paths(data_processed)
        data_rotated = rotate_paths(data_processed)
        data_final_point_on_x_axis = set_final_point_on_x_axis(data_rotated)
        self.data_rotated = np.vstack(
            [
                path[:, 0] for path in data_rotated
            ]  # Selects only the first coordinate, keeping the shape as (T, 1)
        )
        self.data_final_point_on_x_axis = data_final_point_on_x_axis
        self.compute_distance_matrix(data_processed)
        variables = compute_paths_variables(data_processed)
        variables = [np.array(path) for path in variables]
        self.variables = variables

    def compute_distance_matrix(self, data):
        n_samples = len(data)
        self.dist_matrix = np.zeros((n_samples, n_samples))
        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                distance_x = dtw(
                    data[i][:, 0],
                    data[j][:, 0],
                    global_constraint="sakoe_chiba",
                    sakoe_chiba_radius=3,
                )
                distance_y = dtw(
                    data[i][:, 1],
                    data[j][:, 1],
                    global_constraint="sakoe_chiba",
                    sakoe_chiba_radius=3,
                )
                self.dist_matrix[i, j] = self.dist_matrix[j, i] = (
                    distance_x + distance_y
                )

    def initialize_models(self, num_clusters):
        self.model_1 = KMedoids(
            n_clusters=num_clusters, random_state=0, metric="precomputed"
        )
        self.model_2 = KMeans(n_clusters=num_clusters, random_state=0)
        self.model_3 = KMeans(n_clusters=num_clusters, random_state=0)

    def train(self):
        self.model_1.fit(self.dist_matrix)
        self.model_2.fit(self.variables)
        self.model_3.fit(self.data_rotated)

        self.make_labels_congruent(self.debug)

    @staticmethod
    def difference(y_true, y_pred):
        return np.sum(y_true != y_pred)

    def make_labels_congruent(self, debug=False):
        # Assuming each model's labels are stored in self.model_{i}.labels_
        labels = [self.model_1.labels_, self.model_2.labels_, self.model_3.labels_]

        # Generate all permutations of the labels for 3 clusters
        label_permutations = list(
            permutations(range(len(self.model_2.cluster_centers_)))
        )

        # Initialize variables to track the minimum cross-entropy and best permutations
        min_cross_entropy = float("inf")
        best_mappings = None

        # Iterate over all possible permutations for the three sets of labels
        for perm1, perm2, perm3 in product(label_permutations, repeat=3):
            # Apply the permutations
            permuted_labels1 = np.array([perm1[label] for label in labels[0]])
            permuted_labels2 = np.array([perm2[label] for label in labels[1]])
            permuted_labels3 = np.array([perm3[label] for label in labels[2]])

            # Calculate the "cross-entropy" for this permutation
            # Placeholder for actual cross-entropy calculation
            cross_entropy = (
                self.difference(permuted_labels1, permuted_labels2)
                + self.difference(permuted_labels1, permuted_labels3)
                + self.difference(permuted_labels2, permuted_labels3)
            )

            # Update the minimum cross-entropy and best mappings if current is better
            if cross_entropy < min_cross_entropy:
                min_cross_entropy = cross_entropy
                best_mappings = (perm1, perm2, perm3)

        # store the alligned labels
        self.aligned_labels_1 = best_mappings[0]
        self.aligned_labels_2 = best_mappings[1]
        self.aligned_labels_3 = best_mappings[2]

        if debug:
            print(f"Best mappings: {best_mappings}")
            print(f"Minimized cross-entropy: {min_cross_entropy}")

    def plot_dendrogram(self):
        # Compute and plot the dendrogram
        linkage_matrix = linkage(squareform(self.dist_matrix), method="ward")
        dendrogram(linkage_matrix)
        plt.show()

    def plot_clusters(self):
        # Plot the clusters
        plt.scatter(
            self.data_final_point_on_x_axis[:, 0],
            self.data_final_point_on_x_axis[:, 1],
            c=self.aligned_labels_1,
        )
        plt.show()

    def predict(self, path):
        segmented_paths = segment_path_to_given_length(path, self.length_paths)
        segmented_paths = recenter_paths(segmented_paths)
        segmented_paths = rotate_paths(segmented_paths)
        segmented_paths = set_final_point_on_x_axis(segmented_paths)

        predictions = []
        for path_segment in segmented_paths:
            variables = np.array(compute_path_variables(path_segment))
            medoids = self.model_1.medoid_indices_
            centers_model_1 = [self.data_final_point_on_x_axis[i] for i in medoids]

            minimal_distance = float("inf")
            label_1 = -1

            for i in range(len(centers_model_1)):
                distance_x = dtw(
                    path_segment[:, 0],
                    centers_model_1[i][:, 0],
                    global_constraint="sakoe_chiba",
                    sakoe_chiba_radius=3,
                )
                distance_y = dtw(
                    path_segment[:, 1],
                    centers_model_1[i][:, 1],
                    global_constraint="sakoe_chiba",
                    sakoe_chiba_radius=3,
                )
                distance = distance_x + distance_y
                if distance < minimal_distance:
                    minimal_distance = distance
                    index = i

            label_2 = self.model_2.predict(variables.reshape(1, -1))[0]
            segment = path_segment[:, 0]
            label_3 = self.model_3.predict(segment.reshape(1, -1))[0]

            # Use congruent labels
            label_1 = self.aligned_labels_1[label_1]
            label_2 = self.aligned_labels_2[label_2]
            label_3 = self.aligned_labels_3[label_3]

            # Collect predictions from all models for the segment
            predictions.append([label_1, label_2, label_3])

        # Flatten the list of predictions and find the mode across all models for all segments
        flattened_predictions = [pred for sublist in predictions for pred in sublist]
        return mode(flattened_predictions)[0]

    def detect_anomaly(self, new_path, threshold=120):
        segmented_paths = segment_path_to_given_length(new_path, self.length_paths)
        segmented_paths = recenter_paths(segmented_paths)
        segmented_paths = rotate_paths(segmented_paths)
        segmented_paths = set_final_point_on_x_axis(segmented_paths)

        is_anomalous = []

        for path_segment in segmented_paths:
            anomaly_count = 0

            variables = np.array(compute_path_variables(path_segment))
            medoids = self.model_1.medoid_indices_
            centers_model_1 = [self.data_final_point_on_x_axis[i] for i in medoids]

            minimal_distance = float("inf")

            for i in range(len(centers_model_1)):
                distance_x = dtw(
                    path_segment[:, 0],
                    centers_model_1[i][:, 0],
                    global_constraint="sakoe_chiba",
                    sakoe_chiba_radius=3,
                )
                distance_y = dtw(
                    path_segment[:, 1],
                    centers_model_1[i][:, 1],
                    global_constraint="sakoe_chiba",
                    sakoe_chiba_radius=3,
                )
                distance = distance_x + distance_y
                if distance < minimal_distance:
                    minimal_distance = distance

            if minimal_distance > threshold:
                anomaly_count += 1

            # get distance from the closest cluster center
            distance_2 = np.min(self.model_2.transform(variables.reshape(1, -1)))
            if distance_2 > threshold:
                anomaly_count += 1

            distance_3 = np.min(
                self.model_3.transform(path_segment[:, 0].reshape(1, -1))
            )
            if distance_3 > threshold:
                anomaly_count += 1

            if anomaly_count > 1:
                is_anomalous.append(1)
            else:
                is_anomalous.append(0)

        return mode(is_anomalous)[0]

    def info(self):
        # print the centers of the clusters of model 2
        centers = self.model_2.cluster_centers_
        # vcl = culvilinear_velocity(path)
        # vsl = straight_line_velocity(path)
        # vap = average_line_velocity(path)
        # lin = linearity_progressive_motility(path)
        # wob = culvilinear_path_wobbling(path)
        # str_a = average_path_straightness(path)
        # bcf = average_path_crossing_colvilinear_path(path)
        # mad = mean_angular_displacement(path)
        for i in range(len(centers)):
            print("Center Index Congruent Label: ", self.aligned_labels_2[i])
            print("vcl: ", centers[i][0])
            print("vsl: ", centers[i][1])


if __name__ == "__main__":
    #  load all the files in "../../data/sample_1_paths/"
    #  and store them in the list "data"
    data = []
    # for each file in the directory
    for filename in os.listdir("../../data/path_extraction/sample_1_paths/dof/"):
        # load the file
        path = np.load("../../data/path_extraction/sample_1_paths/dof/" + filename)
        # append the path to the data list
        data.append(path)

    expert = MixtureOfExperts(data, debug=False, num_clusters=4)
    expert.train()
    expert.info()

    # try infering data[1]
    print(expert.predict(data[1]))
    print(expert.detect_anomaly(data[1], threshold=120))