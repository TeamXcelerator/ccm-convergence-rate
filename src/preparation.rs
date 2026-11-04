//! External data preparation after acquisition; source joins remain Toolkit-owned.
use crate::{journal::Journal, MeasureRequest as Common};
use anyhow::{Context, Result};
use std::{
    fs::{self, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    time::Instant,
};
use xc_cache::ArtifactCacheContext;
use xc_spectral::ccm::{
    self,
    hp::{capture_run::RetainedCcmRun, HighPrecConfig},
    CcmParams,
};
fn save(path: &Path, value: &impl serde::Serialize) -> Result<()> {
    let mut output = OpenOptions::new().write(true).create_new(true).open(path)?;
    serde_json::to_writer_pretty(&mut output, value)?;
    output.write_all(b"\n")?;
    output.sync_all()?;
    Ok(())
}

fn scalar_limit(input: &mut ccm::extended_research::ExternalResearchInputs, bytes: u64) {
    if let Some(finite) = &mut input.finite_diagnostics {
        finite.streaming_options.maximum_stream_scalar_bytes = bytes;
    }
}

/// Explicit supplemental arithmetic data; never a primary/root reference.
pub struct ArithmeticReferenceSelection {
    identity: xc_zeta::zeros::ReferenceZeroDatasetIdentity,
    json: Vec<u8>,
    _resident: xc_core::MemoryReservation,
}

impl ArithmeticReferenceSelection {
    pub fn binding(&self) -> serde_json::Value {
        serde_json::json!({"identity":self.identity,
            "scope":"explicit supplemental arithmetic ordinate extension; primary/root reference unchanged"})
    }

    pub fn install(self, run: &mut RetainedCcmRun) -> Result<()> {
        // The pre-acquisition reservation stays live through the Toolkit's
        // owned transfer. The short conservative overlap avoids an uncharged
        // byte owner during the handoff; it adds no allocation or arithmetic.
        run.set_arithmetic_reference_dataset(self.identity, self.json)
    }
}

fn bounded_reference_file(path: &Path, limit: u64) -> Result<Vec<u8>> {
    let file = fs::File::open(path)?;
    let size = file.metadata()?.len();
    anyhow::ensure!(
        size > 0 && size <= limit,
        "arithmetic reference file exceeds its input limit"
    );
    let mut bytes = Vec::new();
    bytes.try_reserve_exact(usize::try_from(
        size.checked_add(1)
            .context("reference input size overflow")?,
    )?)?;
    file.take(size + 1).read_to_end(&mut bytes)?;
    anyhow::ensure!(
        bytes.len() as u64 == size,
        "arithmetic reference file changed while reading"
    );
    Ok(bytes)
}

fn load_arithmetic_reference_paths(
    n_modes: usize,
    json_path: &Path,
    identity_path: &Path,
    resources: &xc_core::RunResources,
) -> Result<ArithmeticReferenceSelection> {
    let size = fs::metadata(json_path)?.len();
    anyhow::ensure!(
        size > 0 && size <= 64 * 1024 * 1024,
        "arithmetic reference JSON must be nonempty and at most64MiB"
    );
    let resident = resources.try_reserve_retained(
        size.checked_mul(2)
            .and_then(|n| n.checked_add(64 * 1024))
            .context("reference reservation overflow")?,
    )?;
    let identity_bytes = bounded_reference_file(identity_path, 16 * 1024)?;
    let identity: xc_zeta::zeros::ReferenceZeroDatasetIdentity =
        serde_json::from_slice(&identity_bytes)?;
    let prefix = n_modes - n_modes.min(64);
    anyhow::ensure!(
        identity.record_count >= prefix,
        "explicit arithmetic reference has{}records but N={}requires{}prefix ordinates",
        identity.record_count,
        n_modes,
        prefix
    );
    let json = bounded_reference_file(json_path, size)?;
    ccm::research_prepare::validate_arithmetic_reference_dataset(
        ccm::research_prepare::ArithmeticReferenceDataset {
            identity: &identity,
            json: &json,
        },
        resources,
    )?;
    Ok(ArithmeticReferenceSelection {
        identity,
        json,
        _resident: resident,
    })
}

pub fn arithmetic_reference_selection(
    n_modes: usize,
    journal: &Journal,
) -> Result<Option<ArithmeticReferenceSelection>> {
    // The explicit extension is only for the formerly unsupported prefix.
    // Small configurations retain the original bundled producer byte for byte.
    if n_modes - n_modes.min(64) <= 1000 {
        return Ok(None);
    }
    let json = std::env::var_os("XC_ARITHMETIC_REFERENCE_JSON");
    let identity = std::env::var_os("XC_ARITHMETIC_REFERENCE_IDENTITY");
    let (json, identity) = match (json, identity) {
        (None, None) => return Ok(None),
        (Some(json), Some(identity)) => (PathBuf::from(json), PathBuf::from(identity)),
        _ => anyhow::bail!("explicit arithmetic reference requires both JSON and identity files"),
    };
    let resources = xc_core::RunResources::current()
        .context("arithmetic reference needs an admitted run resource owner")?;
    let selection = load_arithmetic_reference_paths(n_modes, &json, &identity, &resources)?;
    journal.save_bytes("arithmetic-reference-ordinates.json", &selection.json)?;
    journal.save("arithmetic-reference-identity.json", &selection.binding())?;
    Ok(Some(selection))
}

pub fn target_binding() -> Result<serde_json::Value> {
    let Some(path) = std::env::var_os("XC_TARGET_SPEC_FILE") else {
        anyhow::ensure!(
            std::env::var_os("XC_RESEARCH_PREPARER").is_none(),
            "external preparation requires a target specification before acquisition"
        );
        return Ok(serde_json::json!({}));
    };
    let path = PathBuf::from(path);
    let bytes = xc_spectral::target::read_target_specification(&path)?;
    Ok(
        serde_json::json!({"XC_TARGET_SPEC_FILE":{"status":"supplied",
        "sha256":xc_cache::ContentDigest::sha256(&bytes),"path":path}}),
    )
}

pub fn prepare(
    run: &mut RetainedCcmRun,
    params: &CcmParams,
    cfg: &HighPrecConfig,
    args: &Common,
    cache: &ArtifactCacheContext<'_>,
    journal: &Journal,
    target_binding: &serde_json::Value,
) -> Result<serde_json::Value> {
    let mut base = run.prepare_extended_research_inputs()?;
    if let Some(input) = &mut base {
        scalar_limit(input, args.capture_maximum_stream_scalar_bytes);
        run.set_extended_research_inputs(input.clone())?;
    }
    let configuration = match std::env::var("XC_RESEARCH_PREPARER") {
        Ok(configuration) => configuration,
        Err(std::env::VarError::NotPresent) => {
            return Ok(serde_json::json!({
            "status":"not_configured", "scope":"missing external inputs remain explicit in the receipt"}))
        }
        Err(error) => return Err(error.into()),
    };
    let request = serde_json::json!({"schema_version":1,
        "configuration":{"lambda_squared":params.lambda_sq_int(),"n_modes":params.n_modes,
            "precision_bits":cfg.precision_bits,"root_precision_policy":cfg.root_precision_policy,
            "research_inputs":target_binding},
        "primary_sources":run.primary_sources(), "base_inputs":base,
        "target_spec_file":target_binding["XC_TARGET_SPEC_FILE"]["path"],
        "output_visibility":"private_only", "primary_recomputation":false});
    let mut prepared = invoke_preparer(&journal.directory, &request, &configuration)?;
    scalar_limit(
        &mut prepared.input,
        args.capture_maximum_stream_scalar_bytes,
    );
    run.set_extended_research_inputs(prepared.input)?;
    let components = run.prepare_retained_trial_components(
        320,
        ccm::capture_runtime::RESEARCH_INPUT_MAXIMUM_BYTES,
        cache,
    )?;
    Ok(
        serde_json::json!({"status":"prepared","source_join_validated":true,
        "input_sha256":prepared.digest,"primary_recomputed":false,"root_recomputed":false,
        "retained_trial_components":components,
        "scope":"absolute bounds and finite interpolant scope remain qualified in the diagnostics"}),
    )
}
// An explicitly configured private adapter runs only after primary sources
// exist. The executable and recipe stay outside the public paper repository.
// Its output is data and must pass the Toolkit's authenticated source join.
#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct InputPreparer {
    argv: Vec<String>,
    // Zero explicitly disables only the elapsed-time cutoff.
    timeout_seconds: u64,
}

impl InputPreparer {
    fn time_limit(&self) -> Option<std::time::Duration> {
        (self.timeout_seconds != 0).then(|| std::time::Duration::from_secs(self.timeout_seconds))
    }
}

#[derive(Debug)]
struct PreparedInputs {
    input: xc_spectral::ccm::extended_research::ExternalResearchInputs,
    digest: xc_cache::ContentDigest,
}

// Operational telemetry deliberately stays out of prepared inputs, source
// identities and capture plans. Never echo adapter stdout/stderr or argv.
struct PreparationProgress {
    started: Instant,
    last_heartbeat: Instant,
    file: fs::File,
    directory: PathBuf,
}

impl PreparationProgress {
    fn new(directory: &Path) -> Result<Self> {
        Ok(Self {
            started: Instant::now(),
            last_heartbeat: Instant::now(),
            file: OpenOptions::new()
                .create_new(true)
                .write(true)
                .open(directory.join("input-preparation-progress.jsonl"))?,
            directory: directory.to_path_buf(),
        })
    }

    fn emit(&mut self, stage: &'static str) -> Result<()> {
        self.emit_timed(stage, None)
    }

    fn emit_timed(&mut self, stage: &'static str, validation_seconds: Option<f64>) -> Result<()> {
        let bytes = |name| {
            fs::metadata(self.directory.join(name))
                .map(|m| m.len())
                .unwrap_or(0)
        };
        let event = serde_json::json!({"schema_version":1,"stage":stage,
            "elapsed_seconds":self.started.elapsed().as_secs_f64(),
            "validation_seconds":validation_seconds,
            "stdout_bytes":bytes("input-preparation.stdout.log"),
            "stderr_bytes":bytes("input-preparation.stderr.log"),
            "output_bytes":bytes("prepared-research-inputs.json"),
            "numerical_progress_verified":false});
        serde_json::to_writer(&mut self.file, &event)?;
        self.file.write_all(b"\n")?;
        self.file.sync_data()?;
        self.last_heartbeat = Instant::now();
        xc_core::progress_message!("private preparation: stage={stage}, elapsed={:.1}s; retained logs: input-preparation.stdout.log, input-preparation.stderr.log (private preparation directory); byte counters are operational only", self.started.elapsed().as_secs_f64());
        Ok(())
    }
}

struct PreparerProcess(std::process::Child);
impl Drop for PreparerProcess {
    fn drop(&mut self) {
        // Every descendant that retains the child's process group is
        // stopped on success, failure and timeout, before reading output.
        #[cfg(unix)]
        {
            let _ = std::process::Command::new("/bin/kill")
                .args(["-KILL", "--", &format!("-{}", self.0.id())])
                .stdin(std::process::Stdio::null())
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .status();
        }
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn invoke_preparer(
    directory: &Path,
    request: &serde_json::Value,
    configuration: &str,
) -> Result<PreparedInputs> {
    use std::process::{Command, Stdio};
    anyhow::ensure!(
        cfg!(unix),
        "private input preparation requires Unix process-group supervision"
    );
    #[cfg(unix)]
    anyhow::ensure!(
        Path::new("/bin/kill").is_file(),
        "process-group cleanup executable unavailable"
    );
    let preparer: InputPreparer = serde_json::from_str(configuration)?;
    anyhow::ensure!(
        !preparer.argv.is_empty()
            && preparer.argv.len() <= 16
            && preparer
                .argv
                .iter()
                .all(|a| !a.is_empty() && a.len() <= 32768),
        "invalid private input preparation command"
    );
    let directory = directory.canonicalize()?;
    let mut progress = PreparationProgress::new(&directory)?;
    progress.emit("request_admitted")?;
    match preparer.time_limit() {
        Some(limit) => xc_core::progress_message!(
            "private preparation: configured elapsed-time limit={} seconds",
            limit.as_secs()
        ),
        None => xc_core::progress_message!(
            "private preparation: elapsed-time cutoff disabled (timeout_seconds=0)"
        ),
    }
    // The location is driver-owned and screened independently from adapter
    // output; secret-bearing paths are never echoed to the terminal.
    let location = directory.display().to_string();
    if xc_core::validate_secret_free(&location, "preparation log location").is_ok() {
        xc_core::progress_message!("private preparation log directory: {location}");
    }
    let request_path = directory.join("input-preparation-request.json");
    let output_path = directory.join("prepared-research-inputs.json");
    save(&request_path, request)?;
    let stdout = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(directory.join("input-preparation.stdout.log"))?;
    let stderr = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(directory.join("input-preparation.stderr.log"))?;
    let mut command = Command::new(&preparer.argv[0]);
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = PreparerProcess(
        command
            .args(&preparer.argv[1..])
            .arg("--request")
            .arg(&request_path)
            .arg("--output")
            .arg(&output_path)
            .stdin(Stdio::null())
            .stdout(stdout)
            .stderr(stderr)
            .spawn()
            .context("starting private input preparer")?,
    );
    let started = Instant::now();
    progress.emit("process_started")?;
    let status = loop {
        if let Some(status) = child.0.try_wait()? {
            break status;
        }
        let excessive = [
            "input-preparation.stdout.log",
            "input-preparation.stderr.log",
            "prepared-research-inputs.json",
        ]
        .iter()
        .any(|name| {
            fs::metadata(directory.join(name)).is_ok_and(|m| {
                m.len() > xc_spectral::ccm::capture_runtime::RESEARCH_INPUT_MAXIMUM_BYTES
            })
        });
        if excessive {
            progress.emit("output_budget_exceeded")?;
            anyhow::bail!("private input preparer exceeded its output budget");
        }
        if preparer
            .time_limit()
            .is_some_and(|limit| started.elapsed() >= limit)
        {
            progress.emit("timeout")?;
            anyhow::bail!("private input preparation exceeded its time limit");
        }
        if progress.last_heartbeat.elapsed() >= std::time::Duration::from_secs(30) {
            progress.emit("process_running")?;
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    };
    drop(child);
    progress.emit(if status.success() {
        "process_exited_successfully"
    } else {
        "process_exited_unsuccessfully"
    })?;
    anyhow::ensure!(
        status.success(),
        "private input preparer exited with {status}"
    );
    anyhow::ensure!(
        [
            "input-preparation.stdout.log",
            "input-preparation.stderr.log"
        ]
        .iter()
        .all(|name| fs::metadata(directory.join(name)).is_ok_and(|m| m.len() <= 64 * 1024 * 1024)),
        "private input preparer log exceeds 64 MiB"
    );
    anyhow::ensure!(
        fs::metadata(&output_path)?.len()
            <= xc_spectral::ccm::capture_runtime::RESEARCH_INPUT_MAXIMUM_BYTES,
        "private prepared input exceeds the research input byte limit"
    );
    // Read once: validation, loading and the recorded digest use identical
    // admitted bytes. A changed retained file will fail summary verification.
    use std::io::Read;
    let mut bytes = Vec::new();
    let validation_started = Instant::now();
    progress.emit("validating_prepared_input")?;
    fs::File::open(&output_path)?
        .take(xc_spectral::ccm::capture_runtime::RESEARCH_INPUT_MAXIMUM_BYTES + 1)
        .read_to_end(&mut bytes)?;
    let input = xc_spectral::ccm::extended_research::ExternalResearchInputs::from_bytes(
        &output_path,
        &bytes,
    );
    progress.emit_timed(
        if input.is_ok() {
            "prepared_input_validated"
        } else {
            "prepared_input_validation_failed"
        },
        Some(validation_started.elapsed().as_secs_f64()),
    )?;
    let input = input?;
    Ok(PreparedInputs {
        input,
        digest: xc_cache::ContentDigest::sha256(&bytes),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    struct ReferenceFixture(PathBuf);
    impl ReferenceFixture {
        fn new() -> Self {
            static NEXT: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
            let nonce = NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            let time = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "ccm-reference-input-{}-{time}-{nonce}",
                std::process::id()
            ));
            fs::create_dir(&path).unwrap();
            let mut records = xc_zeta::zeros::bundled_first_n_strings(1000).unwrap();
            // This fixture tests source handling, not a numerical zero claim.
            records.push(format!("2000.{}", "0".repeat(2496)));
            let bytes = serde_json::to_vec(&records).unwrap();
            let identity = xc_zeta::zeros::ReferenceZeroDatasetIdentity {
                schema_version: 1,
                resource_id: "test/paper-reference-extension".into(),
                content_sha256: xc_cache::ContentDigest::sha256(&bytes).0,
                record_count: 1001,
                decimal_digits: 2500,
            };
            fs::write(path.join("ordinates.json"), bytes).unwrap();
            fs::write(
                path.join("identity.json"),
                serde_json::to_vec(&identity).unwrap(),
            )
            .unwrap();
            Self(path)
        }
        fn load(
            &self,
            n: usize,
            resources: &xc_core::RunResources,
        ) -> Result<ArithmeticReferenceSelection> {
            load_arithmetic_reference_paths(
                n,
                &self.0.join("ordinates.json"),
                &self.0.join("identity.json"),
                resources,
            )
        }
    }
    impl Drop for ReferenceFixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn arithmetic_reference_is_owned_and_releases_its_reservation() {
        let fixture = ReferenceFixture::new();
        let resources = xc_core::RunResources::new(256 * 1024 * 1024).unwrap();
        let selection = fixture.load(1065, &resources).unwrap();
        assert_eq!(selection.identity.record_count, 1001);
        assert!(resources.usage().retained_bytes >= selection.json.len() as u64);
        assert_eq!(resources.usage().working_bytes, 0);
        drop(selection);
        assert_eq!(resources.usage().retained_bytes, 0);
    }

    #[test]
    fn arithmetic_reference_rejects_wrong_hash_and_insufficient_prefix() {
        let fixture = ReferenceFixture::new();
        let resources = xc_core::RunResources::new(256 * 1024 * 1024).unwrap();
        assert!(fixture
            .load(1066, &resources)
            .err()
            .unwrap()
            .to_string()
            .contains("requires"));
        let path = fixture.0.join("ordinates.json");
        let mut bytes = fs::read(&path).unwrap();
        bytes.push(b' ');
        fs::write(path, bytes).unwrap();
        assert!(fixture
            .load(1065, &resources)
            .err()
            .unwrap()
            .to_string()
            .contains("digest mismatch"));
        assert_eq!(resources.usage().retained_bytes, 0);
    }

    #[test]
    fn arithmetic_reference_admits_memory_before_reading() {
        let fixture = ReferenceFixture::new();
        let resources = xc_core::RunResources::new(1).unwrap();
        assert!(fixture.load(1065, &resources).is_err());
        assert_eq!(resources.usage().retained_bytes, 0);
        assert!(bounded_reference_file(&fixture.0.join("ordinates.json"), 1).is_err());
    }
    #[test]
    fn invalid_adapter_is_rejected_before_files_or_processes() {
        let result = invoke_preparer(
            Path::new("/nonexistent-preparation-test"),
            &serde_json::json!({}),
            r#"{"argv":[],"timeout_seconds":0}"#,
        );
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("invalid private input preparation command"));
    }
    #[test]
    fn preparation_deadline_is_explicit_not_implicitly_two_hours() {
        let disabled: InputPreparer =
            serde_json::from_str(r#"{"argv":["adapter"],"timeout_seconds":0}"#).unwrap();
        assert!(disabled.time_limit().is_none());
        let bounded: InputPreparer =
            serde_json::from_str(r#"{"argv":["adapter"],"timeout_seconds":60}"#).unwrap();
        assert_eq!(
            bounded.time_limit(),
            Some(std::time::Duration::from_secs(60))
        );
    }
}
