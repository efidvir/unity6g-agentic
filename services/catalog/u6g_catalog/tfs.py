"""What a TeraFlowSDN source tree declares about the devices, drivers, services and KPIs it supports.

The catalog's transport entries rest on these declarations. They are read from the source tree as text and
as Python syntax trees, and nothing in the tree is imported or run:

- proto/kpi_sample_types.proto: the KPI sample types, with their numbers and comments;
- proto/context.proto: the kinds of device driver and of service;
- src/common/DeviceTypes.py: the device types;
- src/device/service/drivers/__init__.py: which driver serves which device types;
- src/service/service/service_handlers/__init__.py: which handler realizes which service type, on which
  drivers;
- src/nbi/service/*/yang/*.yang: the YANG modules of each northbound interface, and the SLO metric types of
  the network slice service;
- src/device/service/drivers/ceragon/portfolio.py: the radio products the Ceragon driver models, and which of
  them were checked against a real device."""

import ast
import re
from pathlib import Path
from typing import Any

ENUM = re.compile(r"enum\s+(?P<name>\w+)\s*\{(?P<body>.*?)\n\s*\}", re.S)
ENUM_VALUE = re.compile(
    r"^\s*(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>\d+)\s*;(?:[ \t]*//\.?[ \t]*(?P<comment>.*))?$", re.M
)
YANG_FILE = re.compile(r"^(?P<module>[A-Za-z0-9_.-]+)@(?P<revision>\d{4}-\d{2}-\d{2})\.yang$")
IDENTITY = re.compile(r"identity\s+(?P<name>[\w-]+)\s*\{(?P<body>.*?)\n  \}", re.S)
DESCRIPTION = re.compile(r'description\s+"(?P<text>[^"]*)"', re.S)
REFERENCE = re.compile(r'reference\s+"(?P<text>[^"]*)"', re.S)


def _clean(text: str) -> str:
    return " ".join(text.split())


def proto_enum(text: str, enum: str) -> list[dict[str, Any]]:
    """The values of one enum of a proto file, in the order written, with the comment that follows each."""
    for match in ENUM.finditer(text):
        if match["name"] == enum:
            values = []
            for value in ENUM_VALUE.finditer(match["body"]):
                item: dict[str, Any] = {"name": value["name"], "value": int(value["value"])}
                if value["comment"] and value["comment"].strip():
                    item["comment"] = _clean(value["comment"])
                values.append(item)
            return values
    raise ValueError(f"enum {enum} not found")


def _attr_name(node: ast.expr) -> str:
    """The attribute named by EnumClass.MEMBER."""
    if isinstance(node, ast.Attribute):
        return node.attr
    raise ValueError(f"unexpected expression {ast.dump(node)}")


def _names(node: ast.expr) -> list[str]:
    if isinstance(node, ast.List | ast.Tuple):
        return [_attr_name(element) for element in node.elts]
    return [_attr_name(node)]


def device_types(text: str) -> dict[str, str]:
    """The members of DeviceTypeEnum and the string each stands for."""
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "DeviceTypeEnum":
            return {
                stmt.targets[0].id: stmt.value.value
                for stmt in node.body
                if isinstance(stmt, ast.Assign)
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            }
    raise ValueError("DeviceTypeEnum not found")


def _filters(registration: ast.expr) -> tuple[str, list[dict[str, list[str]]]]:
    """(class, filters) of one registration written as (Class, [{FilterFieldEnum.X: value, ...}, ...])."""
    if not (isinstance(registration, ast.Tuple) and len(registration.elts) == 2):
        raise ValueError(f"unexpected registration {ast.dump(registration)}")
    cls, filters = registration.elts
    if not (isinstance(cls, ast.Name) and isinstance(filters, ast.List)):
        raise ValueError(f"unexpected registration {ast.dump(registration)}")
    result = []
    for item in filters.elts:
        if not isinstance(item, ast.Dict):
            raise ValueError(f"unexpected filter {ast.dump(item)}")
        result.append(
            {_attr_name(key): _names(value) for key, value in zip(item.keys, item.values, strict=True) if key}
        )
    return cls.id, result


def driver_registry(text: str) -> list[dict[str, Any]]:
    """Each driver class with the device types and driver kinds it serves (DRIVERS.append calls)."""
    registrations = []
    for node in ast.walk(ast.parse(text)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "DRIVERS"
        ):
            cls, filters = _filters(node.args[0])
            for f in filters:
                registrations.append(
                    {
                        "driverClass": cls,
                        "deviceTypes": f.get("DEVICE_TYPE", []),
                        "drivers": f.get("DRIVER", []),
                    }
                )
    return registrations


def handler_registry(text: str) -> list[dict[str, Any]]:
    """Each service handler with the service types and driver kinds it handles (the SERVICE_HANDLERS list)."""
    for node in ast.walk(ast.parse(text)):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "SERVICE_HANDLERS"
            and isinstance(node.value, ast.List)
        ):
            registrations = []
            for element in node.value.elts:
                cls, filters = _filters(element)
                for f in filters:
                    registrations.append(
                        {
                            "handlerClass": cls,
                            "serviceTypes": f.get("SERVICE_TYPE", []),
                            "drivers": f.get("DEVICE_DRIVER", []),
                        }
                    )
            return registrations
    raise ValueError("SERVICE_HANDLERS not found")


def yang_modules(directory: Path) -> list[str]:
    """The modules of a directory of YANG files named module@revision.yang, as module@revision."""
    found = []
    for path in sorted(directory.glob("*.yang")):
        match = YANG_FILE.match(path.name)
        if match:
            found.append(f"{match['module']}@{match['revision']}")
    return found


def northbound(src: Path) -> list[dict[str, Any]]:
    """The northbound interfaces of the NBI component that carry YANG modules, with those modules."""
    interfaces = []
    for directory in sorted((src / "nbi" / "service").iterdir()):
        modules = yang_modules(directory / "yang") if (directory / "yang").is_dir() else []
        if modules:
            interfaces.append({"interface": directory.name, "yang": modules})
    return interfaces


def identities(text: str, base: str) -> list[dict[str, Any]]:
    """The identities of a YANG module derived directly from one base, with description and reference."""
    found = []
    for match in IDENTITY.finditer(text):
        body = match["body"]
        if re.search(rf"^\s*base\s+{re.escape(base)}\s*;", body, re.M):
            item: dict[str, Any] = {"identity": match["name"]}
            description = DESCRIPTION.search(body)
            if description:
                item["description"] = _clean(description["text"])
            reference = REFERENCE.search(body)
            if reference:
                item["reference"] = _clean(reference["text"])
            found.append(item)
    return found


PRODUCT_FIELDS = (
    "model",
    "family",
    "product_line",
    "api_flavor",
)  # the first positional fields of ProductSpec


def portfolio(text: str) -> list[dict[str, Any]]:
    """The products of the Ceragon driver's portfolio: model, family, API flavour and whether the API was
    checked against a real device. Read from the ProductSpec calls, whose first arguments are the model, the
    family, the product line and the API flavour; module-level string constants are resolved."""
    tree = ast.parse(text)
    constants = {
        stmt.targets[0].id: stmt.value.value
        for stmt in tree.body
        if isinstance(stmt, ast.Assign)
        and isinstance(stmt.targets[0], ast.Name)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    }

    def value(node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and node.id in constants:
            return constants[node.id]
        return None

    products = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ProductSpec":
            fields = {name: value(arg) for name, arg in zip(PRODUCT_FIELDS, node.args, strict=False)}
            fields.update({kw.arg: value(kw.value) for kw in node.keywords if kw.arg})
            if isinstance(fields.get("model"), str):
                products.append(
                    {
                        "model": fields["model"],
                        "family": fields.get("family"),
                        "apiFlavor": fields.get("api_flavor"),
                        "apiVerified": fields.get("api_verified") is True,
                    }
                )
    return sorted(products, key=lambda p: (str(p["apiFlavor"]), str(p["model"])))


SLICE_YANG = "src/nbi/service/ietf_network_slice/yang"
SLICE_MODULE = "ietf-network-slice-service"


def read_model(tfs: Path) -> dict[str, Any]:
    """The declarations of a TeraFlowSDN source tree, in the form the catalog's controller binding holds."""
    proto = tfs / "proto"
    src = tfs / "src"
    kpi_text = (proto / "kpi_sample_types.proto").read_text()
    context_text = (proto / "context.proto").read_text()
    types = device_types((src / "common" / "DeviceTypes.py").read_text())
    slice_files = sorted((tfs / SLICE_YANG).glob(f"{SLICE_MODULE}@*.yang"))
    if not slice_files:
        raise ValueError(f"{SLICE_MODULE} not found under {SLICE_YANG}")
    slice_file = slice_files[-1]
    revision = YANG_FILE.match(slice_file.name)
    model: dict[str, Any] = {
        "deviceTypes": [{"name": name, "value": value} for name, value in types.items()],
        "deviceDrivers": proto_enum(context_text, "DeviceDriverEnum"),
        "serviceTypes": proto_enum(context_text, "ServiceTypeEnum"),
        "kpiSampleTypes": proto_enum(kpi_text, "KpiSampleType"),
        "drivers": driver_registry((src / "device" / "service" / "drivers" / "__init__.py").read_text()),
        "serviceHandlers": handler_registry(
            (src / "service" / "service" / "service_handlers" / "__init__.py").read_text()
        ),
        "northbound": northbound(src),
        "sloMetricTypes": {
            "module": f"{SLICE_MODULE}@{revision['revision'] if revision else ''}",
            "identities": identities(slice_file.read_text(), "service-slo-metric-type"),
        },
    }
    ceragon = src / "device" / "service" / "drivers" / "ceragon" / "portfolio.py"
    if ceragon.is_file():
        model["ceragonPortfolio"] = portfolio(ceragon.read_text())
    return model
