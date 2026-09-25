use std::env;

fn sum(values: &[f64]) -> f64 {
    values.iter().copied().sum()
}

fn mean(values: &[f64]) -> f64 {
    sum(values) / values.len() as f64
}

fn sum_squares(values: &[f64]) -> f64 {
    values.iter().map(|value| value * value).sum()
}

fn variance(values: &[f64]) -> f64 {
    let center = mean(values);
    values.iter().map(|value| (value - center) * (value - center)).sum::<f64>()
        / values.len() as f64
}

fn squared_distance(left: &[f64], right: &[f64]) -> f64 {
    left.iter().zip(right).map(|(a, b)| (a - b) * (a - b)).sum()
}

fn mean_absolute_error(left: &[f64], right: &[f64]) -> f64 {
    left.iter().zip(right).map(|(a, b)| (a - b).abs()).sum::<f64>()
        / left.len() as f64
}

fn max_absolute(values: &[f64]) -> f64 {
    values.iter().map(|value| value.abs()).fold(0.0, f64::max)
}

fn dot(left: &[f64], right: &[f64]) -> f64 {
    left.iter().zip(right).map(|(a, b)| a * b).sum()
}

fn norm(values: &[f64]) -> f64 {
    dot(values, values).sqrt()
}

fn covariance(left: &[f64], right: &[f64]) -> f64 {
    let left_mean = mean(left);
    let right_mean = mean(right);
    left.iter().zip(right)
        .map(|(a, b)| (a - left_mean) * (b - right_mean))
        .sum::<f64>() / left.len() as f64
}

fn score_size(length: usize, seed: usize) -> i64 {
    let pattern = [-1.0_f64, -0.5, 0.5, 1.0];
    let left: Vec<f64> = (0..length).map(|index| pattern[(index + seed) % 4]).collect();
    let right: Vec<f64> = left.iter().map(|value| value + 0.5).collect();
    let total = sum(&left);
    let average = mean(&left);
    let spread = variance(&left);
    let self_product = dot(&left, &left);
    let product = dot(&left, &right);
    let squared = squared_distance(&left, &right);
    let euclidean = squared.sqrt();
    let rmsd = (squared / length as f64).sqrt();
    let magnitude = norm(&left);
    if !(-0.01 < total && total < 0.01 && -0.01 < average && average < 0.01 &&
         spread > 0.62 && spread < 0.63 &&
         self_product > length as f64 * 0.6249 && self_product < length as f64 * 0.6251 &&
         product > length as f64 * 0.6249 && product < length as f64 * 0.6251 &&
         squared > length as f64 * 0.2499 && squared < length as f64 * 0.2501 &&
         (euclidean - (length as f64 * 0.25).sqrt()).abs() < 0.01 &&
         rmsd > 0.49 && rmsd < 0.51 &&
         magnitude > (length as f64 * 0.6249).sqrt() &&
         magnitude < (length as f64 * 0.6251).sqrt()) {
        return -1;
    }

    length as i64 * 5 + 251
}

fn run_workload(seed: usize) -> i64 {
    [64_usize, 256, 1024, 8192]
        .iter()
        .copied()
        .enumerate()
        .map(|(index, length)| score_size(length, seed + index))
        .sum()
}

fn statistics_score_size(length: usize) -> i64 {
    let pattern = [-1.0_f64, -0.5, 0.5, 1.0];
    let left: Vec<f64> = (0..length).map(|index| pattern[index % 4]).collect();
    let right: Vec<f64> = left.iter().map(|value| value + 0.5).collect();
    let left_mean = mean(&left);
    let right_mean = mean(&right);
    let left_variance = variance(&left);
    let deviation = left_variance.sqrt();
    let covariance_value = covariance(&left, &right);
    let right_variance = variance(&right);
    let correlation = covariance_value / (left_variance * right_variance).sqrt();
    if !(-0.01 < left_mean && left_mean < 0.01 &&
         left_variance > 0.62 && left_variance < 0.63 &&
         deviation > 0.79 && deviation < 0.80 &&
         covariance_value > 0.62 && covariance_value < 0.63 &&
         correlation > 0.99 && correlation < 1.01) {
        return -1;
    }
    length as i64 * 2 + 211
}

fn statistics_workload(_seed: usize) -> i64 {
    [64_usize, 256, 1024, 8192]
        .iter()
        .copied()
        .map(statistics_score_size)
        .sum()
}

fn similarity_score_size(length: usize) -> i64 {
    let pattern = [-1.0_f64, -0.5, 0.5, 1.0];
    let left: Vec<f64> = (0..length).map(|index| pattern[index % 4]).collect();
    let right: Vec<f64> = left.iter().map(|value| value + 0.5).collect();
    let squared = squared_distance(&left, &right);
    let euclidean = squared.sqrt();
    let rmsd = (squared / length as f64).sqrt();
    let mae = mean_absolute_error(&left, &right);
    let product = dot(&left, &right);
    let cosine = product / (norm(&left) * norm(&right));
    if !((squared - length as f64 * 0.25).abs() < 0.01 &&
         (euclidean - (length as f64 * 0.25).sqrt()).abs() < 0.01 &&
         rmsd > 0.49 && rmsd < 0.51 &&
         mae > 0.49 && mae < 0.51 &&
         (product - length as f64 * 0.625).abs() < 0.01 &&
         cosine > 0.84 && cosine < 0.85) {
        return -1;
    }
    length as i64 * 3 + 187
}

fn similarity_workload(_seed: usize) -> i64 {
    [64_usize, 256, 1024, 8192]
        .iter()
        .copied()
        .map(similarity_score_size)
        .sum()
}

fn main() {
    let arguments: Vec<String> = env::args().collect();
    if arguments.len() != 3 {
        eprintln!("unsupported benchmark invocation");
        std::process::exit(2);
    }
    let workload: fn(usize) -> i64 = match arguments[1].as_str() {
        "science.structural-comparison.v1" => run_workload,
        "science.statistics-matrix.v1" => statistics_workload,
        "science.similarity-distance.v1" => similarity_workload,
        _ => {
            eprintln!("unsupported benchmark invocation");
            std::process::exit(2);
        }
    };
    let loops: u64 = arguments[2].parse().unwrap_or(0);
    if loops == 0 { std::process::exit(2); }
    let mut checksum = 0_i64;
    for repetition in 0..loops {
        checksum = workload(repetition as usize);
        std::hint::black_box(checksum);
    }
    if checksum < 0 { std::process::exit(1); }
    println!("checksum={checksum}");
}
