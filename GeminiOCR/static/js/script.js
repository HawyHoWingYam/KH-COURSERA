let dropArea = document.getElementById('drop-area');
let fileInput = document.getElementById('fileElem');
let preview = document.getElementById('preview');
let processBtn = document.getElementById('process-btn');
let resultsDiv = document.getElementById('results');
let resultsContent = document.getElementById('results-content');
let downloadBtn = document.getElementById('download-btn');
let downloadExcelBtn = document.getElementById('download-excel-btn');
let loading = document.getElementById('loading');
let currentFile = null;
let resultFilename = null;

// Debug logging function
function logElementState(element, message) {
    console.log(`${message}: isHidden=${element.classList.contains('hidden')}, classList=${element.classList}, style=${element.style.display}`);
}

// Log on page load
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM fully loaded");
    logElementState(loading, "Loading element on page load");

    // Force hide the loading element
    loading.classList.add('hidden');
    loading.style.display = 'none';

    console.log("After adding hidden class");
    logElementState(loading, "Loading element after forcing hidden");
});

// Log element state whenever hidden/shown
const originalRemove = DOMTokenList.prototype.remove;
DOMTokenList.prototype.remove = function () {
    if (this.contains('hidden') && this === loading.classList) {
        console.trace("hidden class REMOVED from loading element");
    }
    return originalRemove.apply(this, arguments);
};

const originalAdd = DOMTokenList.prototype.add;
DOMTokenList.prototype.add = function () {
    if (arguments[0] === 'hidden' && this === loading.classList) {
        console.trace("hidden class ADDED to loading element");
    }
    return originalAdd.apply(this, arguments);
};

// Monitor window load event too
window.addEventListener('load', function () {
    console.log("Window fully loaded");
    logElementState(loading, "Loading element on window load");

    // Double-check that loading is hidden
    loading.classList.add('hidden');
    loading.style.display = 'none';
});


// Completely rewrite processImage function with detailed logging
function processImage() {
    console.log("processImage function called");

    if (!currentFile) {
        console.error("No file selected");
        alert("Please select a file first");
        return;
    }

    console.log("Using file:", currentFile.name, "Size:", currentFile.size);

    // Show loading indicator
    loading.classList.remove('hidden');
    loading.style.display = 'flex';
    console.log("Loading indicator displayed");

    resultsDiv.classList.add('hidden');

    // Create form data with logging
    let formData = new FormData();
    formData.append('file', currentFile);
    const invoiceType = document.getElementById('invoice-type').value;
    formData.append('invoice_type', invoiceType);
    console.log("Form data created. Invoice type:", invoiceType);

    // Log the request details
    console.log("Sending request to /process");

    // Add a timeout to detect hanging requests
    const timeoutId = setTimeout(() => {
        console.error("Fetch request timed out after 30 seconds");
        loading.classList.add('hidden');
        loading.style.display = 'none';
        alert("Request timed out. Please try again.");
    }, 30000);

    fetch('/process', {
        method: 'POST',
        body: formData
    })
        .then(response => {
            clearTimeout(timeoutId);
            console.log("Received response:", response.status, response.statusText);
            return response.json().catch(e => {
                console.error("Error parsing JSON:", e);
                throw new Error("Server returned invalid JSON");
            });
        })
        .then(data => {
            console.log("Parsed response data:", data);

            // Hide loading indicator
            loading.classList.add('hidden');
            loading.style.display = 'none';

            // Handle response
            if (data.error) {
                console.error("Error from server:", data.error);
                resultsContent.innerHTML = `<p class="error">Error: ${data.error}</p>`;
            } else {
                console.log("Success! Filename:", data.filename);
                resultFilename = data.filename;
                resultsContent.innerHTML = `<pre>${JSON.stringify(data.results, null, 2)}</pre>`;
            }

            resultsDiv.classList.remove('hidden');
        })
        .catch(error => {
            clearTimeout(timeoutId);
            console.error("Fetch error:", error);

            // Hide loading indicator
            loading.classList.add('hidden');
            loading.style.display = 'none';

            // Show error
            resultsContent.innerHTML = `<p class="error">Error: ${error.message}</p>`;
            resultsDiv.classList.remove('hidden');

            alert("Error processing image: " + error.message);
        });
}

// Check if CSS for hidden class is working
document.addEventListener('DOMContentLoaded', function () {
    const styles = window.getComputedStyle(loading);
    console.log("Loading element computed style:", styles.display);
});

// Add these log statements to debug file selection
function handleFiles(files) {
    console.log("handleFiles called", files);
    if (files && files.length) {
        currentFile = files[0];
        console.log("File selected:", currentFile.name, currentFile.type);
        previewFile(currentFile);
        processBtn.disabled = false;
    } else {
        console.log("No files selected or files object is invalid");
    }
}

function previewFile(file) {
    console.log("Previewing file:", file.name);
    let reader = new FileReader();
    reader.onloadend = function (e) {
        console.log("File read complete");
        let img = document.createElement('img');
        img.src = reader.result;
        img.onload = function () {
            console.log("Image loaded successfully");
        };
        img.onerror = function () {
            console.error("Error loading image");
        };
        preview.innerHTML = '';
        preview.appendChild(img);
    };
    reader.onerror = function () {
        console.error("Error reading file");
    };
    try {
        reader.readAsDataURL(file);
        console.log("Started reading file");
    } catch (err) {
        console.error("Exception when reading file:", err);
    }
}

// Make sure the input element has proper event listener
document.addEventListener('DOMContentLoaded', function () {
    // Re-attach event listener to file input
    fileInput.addEventListener('change', function (e) {
        console.log("File input changed");
        handleFiles(this.files);
    });
});


// Add this debugging code for the process button
document.addEventListener('DOMContentLoaded', function () {
    console.log("Process button element:", processBtn);

    // Re-attach event listener directly
    processBtn.onclick = function (e) {
        console.log("Process button clicked via onclick");
        processImage();
    };

    // Also log when the button becomes enabled
    const originalDisabledSetter = Object.getOwnPropertyDescriptor(HTMLButtonElement.prototype, 'disabled').set;
    Object.defineProperty(processBtn, 'disabled', {
        set: function (value) {
            console.log("Process button disabled changed to:", value);
            originalDisabledSetter.call(this, value);
        }
    });
});

downloadBtn.addEventListener('click', () => {
    if (resultFilename) {
        window.location.href = `/download/${resultFilename}`;
    }
});

downloadExcelBtn.addEventListener('click', () => {
    if (resultFilename) {
        window.location.href = `/download-excel/${resultFilename}`;
    }
});