/*
Generic Test Harness (Node/JavaScript) — the JS counterpart of
python_harness.py. Same schema, same approach: dynamic, runs test cases
at runtime via require() rather than codegen, since JS (like Python) can
inspect an arbitrary module's exports without knowing its shape ahead of
time.

Usage: node js_harness.js <path_to_submission.js> <path_to_test_cases.json>
Prints one JSON blob to stdout: {"results": [{id, category, passed, error}, ...]}

Submission contract: the student's file must `module.exports` an object
whose keys are the function names referenced by test_cases[].function.
*/
const fs = require("fs");

const submissionPath = process.argv[2];
const testCasesPath = process.argv[3];

const testCases = JSON.parse(fs.readFileSync(testCasesPath, "utf8"));

let mod;
try {
    mod = require(submissionPath);
} catch (e) {
    console.log(JSON.stringify({
        results: [{id: "IMPORT", category: "structure", passed: false, error: `${e.constructor.name}: ${e.message}`}],
    }));
    process.exit(0);
}

const results = [];
for (const tc of testCases) {
    const fn = mod[tc.function];
    if (typeof fn !== "function") {
        results.push({id: tc.id, category: tc.category, passed: false,
                       error: `missing required function '${tc.function}' (check your module.exports)`});
        continue;
    }
    try {
        const actual = fn(...tc.args);
        if ("expect_raises" in tc) {
            results.push({id: tc.id, category: tc.category, passed: false,
                           error: `expected ${tc.expect_raises} but got return value ${JSON.stringify(actual)}`});
        } else if (JSON.stringify(actual) === JSON.stringify(tc.expected)) {
            results.push({id: tc.id, category: tc.category, passed: true, error: null});
        } else {
            results.push({id: tc.id, category: tc.category, passed: false,
                           error: `expected ${JSON.stringify(tc.expected)}, got ${JSON.stringify(actual)}`});
        }
    } catch (e) {
        if ("expect_raises" in tc && e.constructor.name === tc.expect_raises) {
            results.push({id: tc.id, category: tc.category, passed: true, error: null});
        } else {
            results.push({id: tc.id, category: tc.category, passed: false,
                           error: `${e.constructor.name}: ${e.message}`});
        }
    }
}
console.log(JSON.stringify({results}));
