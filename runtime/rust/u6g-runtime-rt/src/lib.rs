//! The real-time runtime core of the UNITY-6G agentic framework (guide Section 3.8).
//! Work item 4.1 builds it; the crate exists from the first commit so that the workspace builds.

/// The version of the runtime core.
pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    #[test]
    fn version_is_set() {
        assert!(!super::version().is_empty());
    }
}
