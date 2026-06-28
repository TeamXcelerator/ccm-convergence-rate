// Copyright (c) 2026 Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))
// All rights reserved. See LICENSE file for terms.
//
// This source code is provided for verification and study purposes only.
// Modification, redistribution, and commercial use are prohibited
// without explicit written permission.

//! CCM Zeta Spectral Triple — Convergence Formula
//!
//! Numerical investigation of the empirical convergence formula
//! D(λ², N, P) = min(D_prec, D_modes, D_primes) for the
//! Connes–Consani–Moscovici operator construction (arXiv:2511.22755).
//!
//! Author: Ronnie Andrews, Jr. (Team Xcelerator Inc.(R))

use anyhow::Result;
use clap::{Parser, Subcommand};
use std::path::Path;

use xc_spectral::ccm::{self, CcmParams};

/// Path to the canonical reference zeros file.
const ZEROS_PATH: &str = "data/zeta_zeros.json";

#[derive(Parser)]
#[command(
    name = "ccm-convergence-rate",
    about = "CCM Zeta Spectral Triple — convergence formula measurement"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Run the CCM construction and measure matching digits D(λ², N, P).
    /// Used to populate convergence_data.csv and isolate formula blocks.
    Measure {
        /// λ² value (integer, e.g. 13, 100, 1000).
        /// Primes p ≤ λ² enter the Weil form.
        #[arg(long, default_value_t = 13_u64)]
        lambda_sq: u64,

        /// Mode cutoff N. Matrix size is 2N+1.
        #[arg(long, default_value_t = 120)]
        n_modes: usize,

        /// Working precision in decimal digits (requires --features hp).
        #[arg(long, default_value_t = 200)]
        precision_digits: u32,

        /// How many leading eigenvalues to compare against Riemann zeros.
        #[arg(long, default_value_t = 5)]
        top: usize,

        /// Significant digits to display per value.
        #[arg(long, default_value_t = 16)]
        display_digits: usize,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Command::Measure {
            lambda_sq,
            n_modes,
            precision_digits,
            top,
            display_digits,
        } => {
            if lambda_sq < 2 {
                anyhow::bail!("lambda_sq must be >= 2 (got {lambda_sq})");
            }
            let params = CcmParams::from_lambda_sq_integer(lambda_sq, n_modes);
            let primes = ccm::prime_powers_up_to(params.lambda_sq_int());
            println!(
                "CCM operator: λ²={}, N={}, matrix_size={}",
                lambda_sq, params.n_modes, params.matrix_size()
            );
            println!(
                "  prime powers k ≤ {}: {} entries",
                lambda_sq, primes.len()
            );

            #[cfg(feature = "hp")]
            {
                println!("  precision: {} decimal digits", precision_digits);
                let mut cfg = ccm::hp::HighPrecConfig::for_decimal_digits(precision_digits);

                match std::env::var("XC_CACHE_MODE").as_deref() {
                    Ok("off") => {
                        cfg.cache_mode = xc_numerics::quadrature::CacheMode::Off;
                        println!("  cache mode: OFF (no read, no write — pure compute)");
                    }
                    Ok("local") => {
                        cfg.cache_mode = xc_numerics::quadrature::CacheMode::JsonZip;
                        println!("  cache mode: LOCAL (read/write local disk, no network)");
                    }
                    Ok("fetch") => {
                        cfg.cache_mode = xc_numerics::quadrature::CacheMode::DynamicFetch;
                        println!("  cache mode: FETCH (local disk + remote fetch, default)");
                    }
                    Ok(other) => {
                        eprintln!("  WARNING: unknown XC_CACHE_MODE '{}'; using default (fetch)", other);
                    }
                    _ => {}
                }

                let zero_strings = xc_zeta::zeros::first_n_strings(
                    Path::new(ZEROS_PATH),
                    cfg.n_eigenvalues.max(top),
                )?;
                let prec = cfg.precision_bits;
                let zero_seeds: Vec<rug::Float> = zero_strings
                    .iter()
                    .map(|s| rug::Float::with_val(prec, rug::Float::parse(s).unwrap()))
                    .collect();

                let hp_result = ccm::hp::run(&params, &cfg, &zero_seeds)?;

                println!(
                    "  solved in {:.3}s, ε_N = {}",
                    hp_result.elapsed_seconds,
                    xc_numerics::fmt::display_hp(&hp_result.weil_min_eigenvalue, 6)
                );

                let n_compare = top.min(hp_result.eigenvalues_pos.len());
                let ref_strings =
                    xc_zeta::zeros::first_n_strings(Path::new(ZEROS_PATH), n_compare)?;
                let cmp_prec = hp_result.precision_bits * 2;

                println!(
                    "\n{:>4}  {:>22}  {:>22}  {:>14}",
                    "k", "computed eigenvalue", "Riemann zero t_k", "matching digits"
                );
                println!("{}", "-".repeat(68));

                for (k, (eig, ref_str)) in hp_result
                    .eigenvalues_pos
                    .iter()
                    .zip(ref_strings.iter())
                    .enumerate()
                    .take(n_compare)
                {
                    let ref_val = rug::Float::with_val(
                        cmp_prec,
                        rug::Float::parse(ref_str).unwrap(),
                    );
                    match eig {
                        ccm::hp::EigenvalueResult::Converged(eig)
                        | ccm::hp::EigenvalueResult::Approximate(eig) => {
                            let eig_hp = rug::Float::with_val(cmp_prec, eig);
                            let matching =
                                xc_numerics::fmt::matching_digits(&eig_hp, &ref_val);
                            println!(
                                "{:>4}  {:>22}  {:>22}  {:>14}",
                                k + 1,
                                xc_numerics::fmt::display_hp(&eig_hp, display_digits),
                                xc_numerics::fmt::display_hp(&ref_val, display_digits),
                                xc_numerics::fmt::display_hp(&matching, 6),
                            );
                        }
                        ccm::hp::EigenvalueResult::Failed => {
                            println!(
                                "{:>4}  {:>22}  {:>22}  {:>14}",
                                k + 1, "Newton failed",
                                xc_numerics::fmt::display_hp(&ref_val, display_digits),
                                "N/A",
                            );
                        }
                    }
                }
            }
            #[cfg(not(feature = "hp"))]
            {
                let _ = (precision_digits, top, display_digits);
                anyhow::bail!(
                    "High-precision tier requires --features hp at build time.\n\
                     Build with: cargo build --release --features hp"
                );
            }
        }
    }

    Ok(())
}
