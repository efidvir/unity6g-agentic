//! Usage: u6g-typegen <schemas_dir> <out_dir>
//! Work item 0.1 provides the entry point; work item 0.2 adds the generation.

use std::path::Path;
use std::process::ExitCode;

fn count_schemas(dir: &Path) -> usize {
    let Ok(entries) = std::fs::read_dir(dir) else { return 0 };
    entries
        .flatten()
        .map(|e| e.path())
        .map(|p| {
            if p.is_dir() {
                count_schemas(&p)
            } else if p.to_string_lossy().ends_with(".schema.json") {
                1
            } else {
                0
            }
        })
        .sum()
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 2 {
        eprintln!("usage: u6g-typegen <schemas_dir> <out_dir>");
        return ExitCode::from(2);
    }
    let found = count_schemas(Path::new(&args[0]));
    if found > 0 {
        eprintln!("u6g-typegen: {found} schemas found, and the generator arrives with work item 0.2");
        return ExitCode::from(1);
    }
    println!("u6g-typegen: no schemas under {}; nothing to generate", args[0]);
    ExitCode::SUCCESS
}
