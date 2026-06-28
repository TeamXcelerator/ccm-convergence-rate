// Copyright (c) 2026 Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))
// All rights reserved. See LICENSE file for terms.

//! Integration tests for the ccm-convergence-rate binary.
//!
//! Verify that the toolkit dependency is correctly wired and
//! the binary produces expected values for known configurations.

use xc_spectral::ccm::{CcmParams, prime_powers_up_to};

/// CcmParams should produce correct values for the headline config.
#[test]
fn headline_config_params() {
    let params = CcmParams::from_lambda_sq_integer(13, 120);
    assert!((params.lambda_squared() - 13.0).abs() < 1e-12);
    assert_eq!(params.matrix_size(), 241);
}

/// Prime powers up to λ²=13 should give 9 entries (the CCM headline).
#[test]
fn prime_powers_lambda_sq_13() {
    let pp = prime_powers_up_to(13);
    assert_eq!(pp.len(), 9, "λ²=13 should have 9 prime powers");
}

/// Reference zeros file should exist and be loadable.
#[test]
fn reference_zeros_loadable() {
    let path = std::path::Path::new("data/zeta_zeros.json");
    assert!(path.exists(), "data/zeta_zeros.json must exist");
    let zeros = xc_zeta::zeros::first_n_f64(path, 10).unwrap();
    assert_eq!(zeros.len(), 10);
    assert!((zeros[0] - 14.134725).abs() < 0.001);
}
