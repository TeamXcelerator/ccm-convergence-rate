use anyhow::Result;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Status {
    Pass,
    Fail,
    Incomplete,
    Unassessed,
    Unsupported,
}
pub fn implementation_digest() -> xc_cache::ContentDigest {
    let sources = [
        include_str!("main.rs"),
        include_str!("journal.rs"),
        include_str!("capture.rs"),
        include_str!("preparation.rs"),
        include_str!("../Cargo.toml"),
        include_str!("../Cargo.lock"),
    ];
    let normalized = sources
        .iter()
        .map(|s| s.replace("\r\n", "\n"))
        .collect::<Vec<_>>();
    xc_cache::ContentDigest::sha256(
        &serde_json::to_vec(&normalized).expect("source strings serialize"),
    )
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Check {
    pub name: String,
    pub category: String,
    pub status: Status,
    pub reason: String,
}
impl Check {
    pub fn new(name: &str, category: &str, status: Status, reason: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            category: category.into(),
            status,
            reason: reason.into(),
        }
    }
}
pub struct Journal {
    pub directory: PathBuf,
}
impl Journal {
    pub fn start(root: &Path, request: &Value) -> Result<Self> {
        fs::create_dir_all(root)?;
        let time = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
        let directory = root.join(format!("run-{time}-{}", std::process::id()));
        fs::create_dir(&directory)?;
        let this = Self { directory };
        this.save("request.json", request)?;
        this.save("build.json",&json!({"software_version":env!("CARGO_PKG_VERSION"),"implementation_digest":implementation_digest(),"toolkit_revision":crate::TOOLKIT_REVISION,"build_info":crate::build_info(),"cargo_lock":include_str!("../Cargo.lock")}))?;
        println!("Run journal: {}", this.directory.display());
        Ok(this)
    }
    pub fn save(&self, name: &str, value: &impl Serialize) -> Result<()> {
        save(&self.directory.join(name), value)
    }
    pub fn save_bytes(&self, name: &str, bytes: &[u8]) -> Result<()> {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(self.directory.join(name))?;
        file.write_all(bytes)?;
        file.sync_all()?;
        Ok(())
    }
}
pub fn save(path: &Path, value: &impl Serialize) -> Result<()> {
    let mut file = OpenOptions::new().write(true).create_new(true).open(path)?;
    serde_json::to_writer_pretty(&mut file, value)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn journals_never_overwrite_evidence() {
        let root = std::env::temp_dir().join(format!(
            "ccm-experiment-journal-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let j = Journal::start(&root, &json!({})).unwrap();
        assert!(j.save("request.json", &json!({"overwrite":true})).is_err());
        fs::remove_dir_all(root).unwrap();
    }
}

// An evenness observer retaining manifests and small stored-state qualification
// records. Eigenpair payloads are parsed transiently and forwarded unchanged;
// vectors are not retained by the observer. All assurance operations delegate.
#[cfg(feature = "hp")]
pub mod source_observer {
    use anyhow::Result;
    use std::sync::Mutex;
    use xc_cache::{
        ArtifactCacheContext, ArtifactKey, ArtifactManifest, ArtifactProductionAssessment,
        ArtifactProductionSink, CacheError, CacheQuality, ContentDigest, ProducedArtifactRecord,
    };

    pub fn with_sources<T>(
        cache: &ArtifactCacheContext<'_>,
        ground_index_policy: crate::GroundIndexPolicy,
        compute: impl FnOnce(&ArtifactCacheContext<'_>) -> Result<T>,
    ) -> Result<(T, Vec<ArtifactManifest>, Vec<serde_json::Value>)> {
        let sink = ManifestObserver::new(
            cache,
            ground_index_policy,
            &[
                "ccm_tau_matrix",
                "ccm_weil_eigenpair",
                "ccm_validation_record",
            ],
        );
        let value = compute(&observing(cache, &sink))?;
        let (mut sources, mut state_resolutions) = sink.finish()?;
        anyhow::ensure!(
            sources.iter().any(|m| m.key.kind == "ccm_tau_matrix")
                && sources
                    .iter()
                    .filter(|m| m.key.kind == "ccm_weil_eigenpair")
                    .count()
                    >= 2
                && sources
                    .iter()
                    .any(|m| m.key.kind == "ccm_validation_record"),
            "evenness returned without its matrix, both eigenstates, and validation record"
        );
        anyhow::ensure!(
            state_resolutions.len() >= 2,
            "evenness returned without both stored-state resolution records"
        );
        sources.sort_by(|a, b| {
            (&a.key.kind, &a.key.logical_key, &a.content_digest.0).cmp(&(
                &b.key.kind,
                &b.key.logical_key,
                &b.content_digest.0,
            ))
        });
        state_resolutions.sort_by_key(|value| {
            value["source_content_digest"]
                .as_str()
                .unwrap_or_default()
                .to_owned()
        });
        Ok((value, sources, state_resolutions))
    }
    struct ManifestObserver<'a> {
        next: Option<&'a dyn ArtifactProductionSink>,
        kinds: &'a [&'a str],
        records: Mutex<Vec<ArtifactManifest>>,
        ground_index_policy: crate::GroundIndexPolicy,
        state_resolutions: Mutex<Vec<serde_json::Value>>,
    }
    impl<'a> ManifestObserver<'a> {
        fn new(
            cache: &'a ArtifactCacheContext<'_>,
            ground_index_policy: crate::GroundIndexPolicy,
            kinds: &'a [&'a str],
        ) -> Self {
            Self {
                next: cache.production_sink,
                kinds,
                records: Mutex::new(Vec::new()),
                ground_index_policy,
                state_resolutions: Mutex::new(Vec::new()),
            }
        }
        fn observe(&self, manifest: &ArtifactManifest) -> Result<(), CacheError> {
            if self.kinds.contains(&manifest.key.kind.as_str()) {
                let mut records = self.records.lock().map_err(|_| {
                    CacheError::InvalidManifest("capture observer lock poisoned".into())
                })?;
                if !records
                    .iter()
                    .any(|r| r.key == manifest.key && r.content_digest == manifest.content_digest)
                {
                    records.push(manifest.clone());
                }
            }
            Ok(())
        }
        fn observe_payload(&self, artifact: &ProducedArtifactRecord) -> Result<(), CacheError> {
            self.observe(&artifact.manifest)?;
            if artifact.manifest.key.kind != "ccm_weil_eigenpair" {
                return Ok(());
            }
            let value: serde_json::Value = serde_json::from_slice(&artifact.payload)
                .map_err(|error| CacheError::InvalidManifest(error.to_string()))?;
            let admission: Option<xc_spectral::ccm::hp::CcmGroundIndexAdmission> =
                serde_json::from_value(
                    value
                        .get("ground_index")
                        .cloned()
                        .unwrap_or(serde_json::Value::Null),
                )
                .map_err(|error| CacheError::InvalidManifest(error.to_string()))?;
            let outcome =
                crate::reported_ground_admission(self.ground_index_policy, admission.as_ref())
                    .map_err(|error| CacheError::InvalidManifest(error.to_string()))?;
            let resolution = value
                .get("stored_state_resolution")
                .filter(|r| r.is_object())
                .ok_or_else(|| {
                    CacheError::InvalidManifest(
                        "evenness state lacks stored resolution evidence".into(),
                    )
                })?;
            let record = serde_json::json!({"source_key":artifact.manifest.key,
                "source_content_digest":artifact.manifest.content_digest,
                "ground_index_policy":self.ground_index_policy,"ground_index_admission":outcome,
                "stored_state_resolution":resolution});
            let mut records = self.state_resolutions.lock().map_err(|_| {
                CacheError::InvalidManifest("state resolution observer lock poisoned".into())
            })?;
            if !records.iter().any(|old| {
                old["source_key"] == record["source_key"]
                    && old["source_content_digest"] == record["source_content_digest"]
            }) {
                records.push(record);
            }
            Ok(())
        }
        fn finish(self) -> Result<(Vec<ArtifactManifest>, Vec<serde_json::Value>)> {
            let sources = self
                .records
                .into_inner()
                .map_err(|_| anyhow::anyhow!("capture observer lock poisoned"))?;
            let resolutions = self
                .state_resolutions
                .into_inner()
                .map_err(|_| anyhow::anyhow!("state resolution observer lock poisoned"))?;
            Ok((sources, resolutions))
        }
    }
    impl ArtifactProductionSink for ManifestObserver<'_> {
        fn contains_dependency_identity(
            &self,
            identity: &xc_cache::PayloadDependencyIdentity,
        ) -> Result<bool, CacheError> {
            self.next.map_or(Ok(false), |next| {
                next.contains_dependency_identity(identity)
            })
        }
        fn retained_canonical_manifest(
            &self,
            identity: &xc_cache::PayloadDependencyIdentity,
        ) -> Result<Option<xc_cache::CanonicalArtifactManifest>, CacheError> {
            self.next
                .map_or(Ok(None), |next| next.retained_canonical_manifest(identity))
        }
        fn retained_canonical_manifest_for_artifact(
            &self,
            key: &ArtifactKey,
            digest: &ContentDigest,
            quality: CacheQuality,
        ) -> Result<Option<xc_cache::CanonicalArtifactManifest>, CacheError> {
            self.next.map_or(Ok(None), |next| {
                next.retained_canonical_manifest_for_artifact(key, digest, quality)
            })
        }
        fn canonical_closure_complete(
            &self,
            identity: &xc_cache::PayloadDependencyIdentity,
        ) -> Result<bool, CacheError> {
            self.next
                .map_or(Ok(false), |next| next.canonical_closure_complete(identity))
        }
        fn mark_canonical_closure_complete(
            &self,
            identity: &xc_cache::PayloadDependencyIdentity,
        ) -> Result<(), CacheError> {
            self.next.map_or(Ok(()), |next| {
                next.mark_canonical_closure_complete(identity)
            })
        }
        fn contains_artifact(
            &self,
            key: &ArtifactKey,
            digest: &ContentDigest,
        ) -> Result<bool, CacheError> {
            self.next
                .map_or(Ok(false), |next| next.contains_artifact(key, digest))
        }
        fn retained_assurance(
            &self,
            key: &ArtifactKey,
            digest: &ContentDigest,
        ) -> Result<Option<ArtifactProductionAssessment>, CacheError> {
            self.next
                .map_or(Ok(None), |next| next.retained_assurance(key, digest))
        }
        fn supports_encoded_records(&self) -> bool {
            self.next
                .is_some_and(|next| next.supports_encoded_records())
        }
        fn requires_produced_payload(&self, key: &ArtifactKey) -> bool {
            key.kind == "ccm_weil_eigenpair"
                || self
                    .next
                    .is_some_and(|next| next.requires_produced_payload(key))
        }
        fn record_encoded(
            &self,
            artifact: xc_cache::EncodedArtifactRecord,
            encoded: &xc_cache::VerifiedEncodedPayload,
            transport: Option<&xc_cache::VerifiedTransportParts>,
        ) -> Result<(), CacheError> {
            if artifact.manifest.key.kind == "ccm_weil_eigenpair" {
                return Err(CacheError::InvalidTransition(
                    "evenness state resolution requires its produced payload".into(),
                ));
            }
            self.observe(&artifact.manifest)?;
            self.next
                .ok_or_else(|| {
                    CacheError::InvalidTransition(
                        "encoded publication has no configured sink".into(),
                    )
                })?
                .record_encoded(artifact, encoded, transport)
        }
        fn record_assurance_requirement(
            &self,
            requirement: xc_cache::ArtifactAssuranceRequirement,
        ) -> Result<(), CacheError> {
            if let Some(next) = self.next {
                next.record_assurance_requirement(requirement)?;
            }
            Ok(())
        }
        fn record_assurance(
            &self,
            attestation: xc_cache::ArtifactAssuranceAttestation,
        ) -> Result<(), CacheError> {
            if let Some(next) = self.next {
                next.record_assurance(attestation)?;
            }
            Ok(())
        }
        fn record_evidence(&self, kind: &str, payload: &[u8]) -> Result<ContentDigest, CacheError> {
            match self.next {
                Some(next) => next.record_evidence(kind, payload),
                None => Ok(ContentDigest::sha256(payload)),
            }
        }
        fn record(&self, artifact: ProducedArtifactRecord) -> Result<(), CacheError> {
            self.observe_payload(&artifact)?;
            if let Some(next) = self.next {
                next.record(artifact)?;
            }
            Ok(())
        }
        fn record_with_verified_encoded(
            &self,
            artifact: ProducedArtifactRecord,
            encoded: &xc_cache::VerifiedEncodedPayload,
        ) -> Result<(), CacheError> {
            self.observe_payload(&artifact)?;
            if let Some(next) = self.next {
                next.record_with_verified_encoded(artifact, encoded)?;
            }
            Ok(())
        }
        fn record_with_verified_transport(
            &self,
            artifact: ProducedArtifactRecord,
            encoded: &xc_cache::VerifiedEncodedPayload,
            transport: &xc_cache::VerifiedTransportParts,
        ) -> Result<(), CacheError> {
            self.observe_payload(&artifact)?;
            if let Some(next) = self.next {
                next.record_with_verified_transport(artifact, encoded, transport)?;
            }
            Ok(())
        }
    }

    fn observing<'a>(
        cache: &ArtifactCacheContext<'a>,
        sink: &'a dyn ArtifactProductionSink,
    ) -> ArtifactCacheContext<'a> {
        ArtifactCacheContext {
            resolver: cache.resolver,
            reference_resolver: cache.reference_resolver,
            acceptance: cache.acceptance,
            ordered_overlays: cache.ordered_overlays.clone(),
            mode: cache.mode,
            write_on_miss: cache.write_on_miss,
            write_visibility: cache.write_visibility,
            requested_assurance: cache.requested_assurance,
            certification_failure_policy: cache.certification_failure_policy,
            production_sink: Some(sink),
        }
    }
}
