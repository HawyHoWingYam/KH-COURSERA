# Frontend Test Specification for Orders Flow

This document specifies all test scenarios for the new Orders processing pipeline in the frontend.

## Test Setup

### Prerequisites
- Next.js dev server running on port 3000
- Backend API running on port 8000 (or configured API_URL)
- Sample test data created in database
- Playwright or Cypress installed for E2E testing

## Test Scenarios

### 1. Upload Page Tests (`/upload`)

#### 1.1 Document Type and Company Selection
- **TC-Upload-001**: User can select a document type from dropdown
  - Should display all available document types
  - Should update company dropdown when document type changes

- **TC-Upload-002**: User can select a company
  - Should only show companies for selected document type
  - Should be disabled if no document type selected

#### 1.2 File Upload
- **TC-Upload-003**: User can select single file for upload
  - Should accept PDF, PNG, JPG, ZIP files
  - Should display file preview for images
  - Should show file size and validation messages

- **TC-Upload-004**: User can select multiple files
  - Should maintain list of selected files
  - Should show total file size
  - Should allow removing individual files

- **TC-Upload-005**: File validation
  - Should reject files > 10MB individually
  - Should reject files > 50MB in total batch
  - Should reject unsupported file types
  - Should display clear error messages

#### 1.3 Mapping File Upload (Optional)
- **TC-Upload-006**: User can upload optional mapping file
  - Should accept .xlsx files only
  - Should show validation for file type and size
  - Should display success indicator when file selected

#### 1.4 Form Submission
- **TC-Upload-007**: Form submission creates Orders pipeline
  - Should POST to `/api/orders` to create new order
  - Should upload each file via `/api/upload`
  - Should create order items for each file
  - Should attach files to order items
  - Should redirect to `/orders/{order_id}` on success

- **TC-Upload-008**: Error handling in upload flow
  - Should handle API failures gracefully
  - Should show user-friendly error messages
  - Should allow retry after failures
  - Should not create partial orders on failure

### 2. AWB Monthly Page Tests (`/awb/monthly`)

#### 2.1 Company and Month Selection
- **TC-AWB-001**: User can select company
  - Should fetch list of companies from API
  - Should load companies on page mount
  - Should show loading state while fetching

- **TC-AWB-002**: User can select month
  - Should show month picker input
  - Should validate month format (YYYY-MM)
  - Should display selected OneDrive folder hint

#### 2.2 File Upload
- **TC-AWB-003**: User can upload summary PDF
  - Should only accept PDF files
  - Should be required field
  - Should show validation error if missing

- **TC-AWB-004**: User can upload employees CSV (optional)
  - Should only accept CSV files
  - Should be optional field
  - Should show validation error if wrong format

#### 2.3 Form Submission
- **TC-AWB-005**: AWB processing redirects to Orders page
  - Should POST to `/api/awb/process-monthly`
  - Should create OcrOrder with discovered invoices
  - Should redirect to `/orders/{order_id}` on success
  - Should show success message before redirect

- **TC-AWB-006**: Error handling in AWB flow
  - Should handle company not found errors
  - Should handle invalid month format
  - Should handle missing PDF file
  - Should display user-friendly error messages

#### 2.7 Success Feedback
- **TC-AWB-007**: User receives success confirmation
  - Should show "✅ Success:" message
  - Should display "Order ID: {id}"
  - Should auto-redirect after 2 seconds
  - Should allow manual redirect via link

### 3. Navigation Tests

#### 3.1 Menu Navigation
- **TC-Nav-001**: OneDrive Sync moved to Admin
  - Should NOT appear on home page
  - Should appear in `/admin` sidebar
  - Should have redirect from old `/awb/sync` URL

- **TC-Nav-002**: Old batch-jobs routes removed
  - Should return 404 for `/batch-jobs`
  - Should return 404 for `/jobs`
  - Should not appear in any navigation menus

#### 3.2 Redirect Tests
- **TC-Nav-003**: Next.js redirects configured
  - Should redirect `/awb/sync` to `/admin/awb/sync` (permanent)
  - Should not show old batch-jobs routes

### 4. API Integration Tests

#### 4.1 Upload Endpoint Behavior
- **TC-API-001**: POST `/api/orders` creates order
  - Should return 201 with order_id
  - Should accept order_name and primary_doc_type_id
  - Should set initial status to DRAFT

- **TC-API-002**: POST `/api/upload` accepts files
  - Should accept multipart file upload
  - Should return file_id and file metadata
  - Should upload to S3 or local storage

- **TC-API-003**: POST `/api/orders/{id}/items` creates items
  - Should accept company_id, doc_type_id, item_name
  - Should return item_id
  - Should associate with parent order

- **TC-API-004**: POST `/api/orders/{id}/items/{itemId}/files` attaches files
  - Should accept file_id
  - Should associate file with order item
  - Should return success response

#### 4.2 AWB Endpoint Behavior
- **TC-API-005**: POST `/api/awb/process-monthly` processes AWB
  - Should accept company_id, month, files
  - Should discover invoices from S3
  - Should create OcrOrder with items
  - Should return order_id and invoices_found count

- **TC-API-006**: Old batch endpoints removed
  - POST `/process` should return 404
  - POST `/process-zip` should return 404
  - POST `/process-batch` should return 404
  - GET `/batch-jobs` should return 404
  - DELETE `/batch-jobs/{id}` should return 404

### 5. User Experience Tests

#### 5.1 Loading States
- **TC-UX-001**: Loading indicators display correctly
  - Companies dropdown shows loading state while fetching
  - Form submit button shows "Processing..." state
  - Page shows appropriate spinners/skeletons

#### 5.2 Form Validation
- **TC-UX-002**: Form validation provides clear feedback
  - Required fields show red asterisks
  - File type validation shows specific errors
  - File size validation shows specific errors

#### 5.3 Success Confirmation
- **TC-UX-003**: User receives clear success feedback
  - Success message shows ✅ icon
  - Displays order ID for reference
  - Auto-redirects after timeout
  - Manual redirect available immediately

### 6. Backward Compatibility Tests

#### 6.1 Deprecated Routes
- **TC-Compat-001**: Old batch-jobs API routes removed
  - No `/process` endpoint accessible
  - No `/process-zip` endpoint accessible
  - No `/process-batch` endpoint accessible
  - No `/batch-jobs` endpoints accessible

- **TC-Compat-002**: Old batch-jobs UI routes removed
  - No `/batch-jobs` page accessible
  - No `/jobs` page accessible

#### 6.2 New Routes Available
- **TC-Compat-003**: New Orders routes are functional
  - `/orders` page loads and displays orders
  - `/orders/{id}` shows order details
  - `/upload` page uses new Orders API
  - `/awb/monthly` redirects to Orders

## Execution Instructions

### Manual Testing
1. Start backend and frontend servers
2. Navigate to each test URL manually
3. Verify behavior matches specifications
4. Test on different screen sizes (mobile, tablet, desktop)

### Automated Testing (Recommended)
```bash
# Install testing dependencies
cd GeminiOCR/frontend
npm install --save-dev @playwright/test @testing-library/react jest

# Run tests
npm test

# Or use Playwright
npx playwright test
```

### Test Data Setup
Create sample data in database:
```sql
INSERT INTO companies (company_name, company_code, active)
VALUES ('Test Company', 'TST', true);

INSERT INTO document_types (type_name, type_code, description)
VALUES ('Air Waybill', 'AWB', 'Air Waybill processing');

INSERT INTO company_document_configs (company_id, doc_type_id, prompt_path, schema_path, active)
VALUES (1, 1, 'prompts/awb.txt', 'schemas/awb.json', true);
```

## Success Criteria

All tests should pass with:
- ✅ No console errors
- ✅ No unhandled promise rejections
- ✅ Correct HTTP status codes
- ✅ Correct data returned from APIs
- ✅ Correct page redirects
- ✅ User receives appropriate feedback

## Known Issues / Notes

- None at this time

## Future Enhancements

- Add WebSocket tests for real-time order progress
- Add accessibility tests (WCAG 2.1 AA compliance)
- Add performance tests (page load time, API response time)
- Add security tests (CSRF tokens, input validation)
