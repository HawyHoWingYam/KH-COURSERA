export default function TemplateFormatPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10 space-y-10 text-gray-900">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Template JSON Format (v2.0)</h1>
        <p className="text-gray-600">
          Special CSV generation relies on a template.json definition uploaded per document type. The
          template describes the output columns, where data originates, and how computed values should
          be evaluated.
        </p>
      </header>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Required Fields</h2>
        <ul className="list-disc space-y-2 pl-6 text-gray-700">
          <li>
            <span className="font-semibold">template_name</span> and <span className="font-semibold">version</span>:
            metadata used for auditing and versioning.
          </li>
          <li>
            <span className="font-semibold">column_order</span>: ordered array describing the final CSV column
            sequence (must match keys in <code>column_definitions</code>).
          </li>
          <li>
            <span className="font-semibold">column_definitions</span>: mapping of column name to its configuration.
          </li>
          <li>
            <span className="font-semibold">source_data</span>: optional, defaults to <code>mapped_csv</code>.
          </li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Column Types</h2>
        <ul className="list-disc space-y-2 pl-6 text-gray-700">
          <li>
            <span className="font-semibold">source</span>: reads a column directly from the mapped DataFrame via
            <code>source_column</code>.
          </li>
          <li>
            <span className="font-semibold">computed</span>: evaluates an expression referencing mapped columns via
            placeholders such as <code>{'{PHONE}'}</code>.
          </li>
          <li>
            <span className="font-semibold">constant</span>: injects a fixed value using <code>value</code>.
          </li>
        </ul>
        <p className="text-gray-600">
          Optional <code>default_value</code> ensures empty cells fall back to a friendly placeholder instead of
          <code>NaN</code>.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Supported Expression Helpers</h2>
        <p className="text-gray-600">
          Computed columns leverage a safe expression engine with a curated helper set:
        </p>
        <ul className="list-disc space-y-2 pl-6 text-gray-700">
          <li><code>concat()</code>, <code>replace()</code>, <code>split()</code>, <code>substring()</code></li>
          <li><code>upper()</code>, <code>lower()</code>, <code>trim()</code></li>
          <li><code>if(condition, true_value, false_value)</code></li>
          <li>Arithmetic operators: <code>+</code>, <code>-</code>, <code>*</code>, <code>/</code></li>
          <li>Comparisons: <code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code>, <code>==</code>, <code>!=</code></li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Example Template</h2>
        <pre className="bg-gray-900 text-green-200 text-sm rounded-lg p-4 overflow-x-auto">
          <code>{`{
  "template_name": "Telecom Invoice Template",
  "version": "2.0",
  "source_data": "mapped_csv",
  "column_order": [
    "Invoice_Number",
    "Invoice_Date",
    "SIM_Card_Number",
    "Clean_Phone_Number",
    "Total_Monthly_Charge",
    "Full_Billing_Address"
  ],
  "column_definitions": {
    "Invoice_Number": {
      "type": "source",
      "source_column": "PHONE",
      "default_value": ""
    },
    "Invoice_Date": {
      "type": "source",
      "source_column": "DATE",
      "default_value": ""
    },
    "SIM_Card_Number": {
      "type": "source",
      "source_column": "SIM_NUMBER",
      "default_value": ""
    },
    "Clean_Phone_Number": {
      "type": "computed",
      "expression": "replace({PHONE}, ' ', '')",
      "default_value": ""
    },
    "Total_Monthly_Charge": {
      "type": "computed",
      "expression": "{BASE_FEE} + {DATA_CHARGE} + {VOICE_CHARGE}",
      "default_value": "0"
    },
    "Full_Billing_Address": {
      "type": "computed",
      "expression": "concat({ADDRESS}, ', ', {CITY}, ', ', {POSTAL_CODE})",
      "default_value": ""
    }
  }
}`}</code>
        </pre>
      </section>

      <section className="space-y-2 text-gray-700">
        <h2 className="text-xl font-semibold">Validation Checklist</h2>
        <ul className="list-disc pl-6 space-y-1">
          <li>Every column listed in <code>column_order</code> must exist in <code>column_definitions</code>.</li>
          <li>Computed expressions only reference mapped CSV column names inside <code>{'{ }'}</code> placeholders.</li>
          <li>Avoid long-running or unsafe logic—only the whitelisted helpers shown above are available.</li>
          <li>Keep version values concise (alphanumeric, dot, dash, underscore). They are used to build S3 object keys.</li>
        </ul>
      </section>
    </div>
  );
}
