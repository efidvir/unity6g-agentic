//! Work item 0.2: the generated Rust types read the examples of the guide and write them back unchanged.

use std::path::PathBuf;

use prost::Message;
use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::Value;
use u6g_types::contracts;
use u6g_types::proto::u6g::logic::v1 as logic;

fn load(name: &str) -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../examples/contracts").join(name);
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    if name.ends_with(".json") {
        serde_json::from_str(&text).unwrap()
    } else {
        serde_yaml::from_str(&text).unwrap()
    }
}

/// Equal JSON values compare equal: 1 and 1.0 are one number, and an optional list or map that is empty is
/// the same as one that is absent, which is how the generated types write it.
fn normalized(value: Value) -> Value {
    let empty = |v: &Value| matches!(v, Value::Array(a) if a.is_empty()) || matches!(v, Value::Object(o) if o.is_empty());
    match value {
        Value::Number(n) => serde_json::json!(n.as_f64().unwrap()),
        Value::Array(items) => Value::Array(items.into_iter().map(normalized).collect()),
        Value::Object(map) => {
            Value::Object(map.into_iter().filter(|(_, v)| !empty(v)).map(|(k, v)| (k, normalized(v))).collect())
        }
        other => other,
    }
}

fn round_trip<T: DeserializeOwned + Serialize>(name: &str) {
    let original = load(name);
    let typed: T = serde_json::from_value(original.clone()).unwrap_or_else(|e| panic!("{name}: {e}"));
    let written = serde_json::to_value(&typed).unwrap();
    assert_eq!(normalized(written), normalized(original), "{name}");
}

fn refused<T: DeserializeOwned>(name: &str, change: impl FnOnce(&mut Value)) {
    let mut value = load(name);
    change(&mut value);
    assert!(serde_json::from_value::<T>(value).is_err(), "{name}: the change was accepted");
}

#[test]
fn descriptor_of_annex_b() {
    round_trip::<contracts::AgentDescriptor>("descriptor/link-assurance.yaml");
}

#[test]
fn runtime_configuration_of_annex_f() {
    round_trip::<contracts::RuntimeConfig>("runtime/runtime-config.de.yaml");
}

#[test]
fn the_four_envelopes() {
    round_trip::<contracts::Observation>("envelope/observation.json");
    round_trip::<contracts::Insight>("envelope/insight.json");
    round_trip::<contracts::Intent>("envelope/intent.json");
    round_trip::<contracts::ExecutionFeedback>("envelope/execution.json");
}

#[test]
fn what_the_schemas_refuse_the_types_refuse() {
    refused::<contracts::Intent>("envelope/intent.json", |v| v["actionType"] = "tx.set-modulation-profile".into());
    refused::<contracts::Intent>("envelope/intent.json", |v| v["envelope"]["verdict"]["kind"] = "maybe".into());
    refused::<contracts::Observation>("envelope/observation.json", |v| v["unexpected"] = 1.into());
    refused::<contracts::Insight>("envelope/insight.json", |v| v["envelope"]["model"]["digest"] = "sha256:9b1e".into());
    refused::<contracts::AgentDescriptor>("descriptor/link-assurance.yaml", |v| v["tuple"]["de"]["mode"] = "half".into());
}

#[test]
fn messages_of_the_logic_service_encode_and_decode() {
    let request = logic::DecideRequest {
        parameters: Some(prost_types::Struct::default()),
        call: Some(logic::Invocation { invocation_id: "call-1".into(), generation: 4, ..Default::default() }),
        ..Default::default()
    };
    let decoded = logic::DecideRequest::decode(request.encode_to_vec().as_slice()).unwrap();
    assert_eq!(decoded, request);
}
