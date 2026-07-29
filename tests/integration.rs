// Copyright (c) 2026 Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))
// All rights reserved. See LICENSE file for terms.

//! Integration tests for the ccm-convergence-rate binary.
//!
//! Verify that the toolkit dependency is correctly wired and
//! the binary produces expected values for known configurations.

use xc_spectral::ccm::{prime_powers_up_to, CcmParams};

/// CcmParams should produce correct values for the headline config.
#[test]
fn headline_config_params() {
    let params = CcmParams::from_lambda_sq_integer(13, 120);
    assert!((params.lambda_squared() - 13.0).abs() < 1e-12);
    assert_eq!(params.matrix_size(), 241);
}

/// Prime powers up to lambda^2=13 should give 9 entries (the CCM headline).
#[test]
fn prime_powers_lambda_sq_13() {
    let pp = prime_powers_up_to(13);
    assert_eq!(pp.len(), 9, "lambda^2=13 should have 9 prime powers");
}

/// Reference zeros are toolkit-owned, integrity-bound, and available without a
/// paper-project data file.
#[test]
fn bundled_reference_zeros_loadable() {
    let identity = xc_zeta::zeros::bundled_dataset_identity().unwrap();
    assert!(identity.record_count >= 10);
    assert!(identity.decimal_digits >= 1000);
    assert_eq!(identity.content_sha256.len(), 64);
    let strings = xc_zeta::zeros::bundled_first_n_strings(10).unwrap();
    let zeros = strings
        .iter()
        .map(|value| value.parse::<f64>().unwrap())
        .collect::<Vec<_>>();
    assert_eq!(zeros.len(), 10);
    assert!((zeros[0] - 14.134725).abs() < 0.001);
}
