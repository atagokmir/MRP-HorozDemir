# User Acceptance Testing Guide
**Horoz Demir MRP System - Stakeholder Review and Testing**

---

## Table of Contents
1. [Testing Overview](#testing-overview)
2. [System Access and Setup](#system-access-and-setup)
3. [User Workflows and Test Scenarios](#user-workflows-and-test-scenarios)
4. [Feature Validation Checklist](#feature-validation-checklist)
5. [Performance and Usability Testing](#performance-and-usability-testing)
6. [Business Process Validation](#business-process-validation)
7. [Acceptance Criteria](#acceptance-criteria)
8. [Issue Reporting Process](#issue-reporting-process)

---

## Testing Overview

### Purpose of User Acceptance Testing
This guide provides structured test scenarios for business stakeholders to validate that the Horoz Demir MRP System meets operational requirements and business objectives. All tests should be performed from an end-user perspective to ensure the system delivers practical value.

### Testing Scope
- **Functional Testing:** All business features and workflows
- **Usability Testing:** Interface design and user experience
- **Integration Testing:** Data flow between system components
- **Performance Testing:** System responsiveness and reliability
- **Mobile Testing:** Functionality across different devices

### Expected Outcomes
- ✅ All business workflows function correctly
- ✅ User interface is intuitive and efficient
- ✅ Data accuracy and integrity maintained
- ✅ Performance meets operational requirements
- ✅ System ready for production deployment

---

## System Access and Setup

### 1. Testing Environment Access
**Frontend Application:** http://localhost:3000  
**API Documentation:** http://localhost:8000/docs  
**System Status:** Both servers must be running for testing

### 2. Test User Accounts
Use these pre-configured accounts for testing different user roles:

```
Administrator Account:
Username: admin@example.com
Password: admin123
Access Level: Full system administration

Manager Account:
Username: manager@example.com
Password: manager123
Access Level: Inventory and reporting management

Clerk Account:
Username: clerk@example.com
Password: clerk123
Access Level: Basic operations only
```

### 3. Browser Requirements
**Recommended Browsers:**
- Chrome 88+ (Primary recommendation)
- Firefox 85+
- Safari 14+
- Edge 88+

**Device Testing:**
- Desktop computers (1920x1080 or higher)
- Tablets (iPad, Android tablets)
- Mobile phones (iOS Safari, Android Chrome)

### 4. Pre-Test Setup
1. Clear browser cache and cookies
2. Ensure stable internet connection
3. Have test data scenarios ready
4. Prepare documentation for issue reporting
5. Set aside 2-3 hours for complete testing

---

## User Workflows and Test Scenarios

### Scenario 1: System Login and Navigation
**Objective:** Validate authentication and basic navigation functionality.

**Test Steps:**
1. Navigate to http://localhost:3000
2. System should redirect to login page
3. Enter test credentials (admin@example.com / admin123)
4. Click "Sign in" button
5. Verify successful login and redirect to dashboard
6. Test navigation to all main sections:
   - Dashboard
   - Products
   - Warehouses
   - Inventory
   - Stock Operations
   - Suppliers
   - Reports
7. Verify logout functionality

**Expected Results:**
- ✅ Login process completes without errors
- ✅ Dashboard displays system metrics
- ✅ All navigation links function correctly
- ✅ User role permissions enforced properly
- ✅ Logout clears session and returns to login

### Scenario 2: Product Management Workflow
**Objective:** Test complete product lifecycle management.

**Test Steps:**
1. Navigate to Products section
2. Click "Add New Product" (if available)
3. Fill in product information:
   - Code: TEST-001
   - Name: Test Product
   - Category: RAW_MATERIALS
   - Unit of Measure: PIECES
   - Minimum Stock Level: 10
   - Critical Stock Level: 5
4. Save the product
5. Verify product appears in product list
6. Search for the created product
7. Edit product information
8. Test product filtering by category
9. Verify data validation (try invalid inputs)

**Expected Results:**
- ✅ Product creation form validates input correctly
- ✅ New product saves and appears in listing
- ✅ Search functionality works accurately
- ✅ Product editing updates data correctly
- ✅ Filtering shows relevant results only
- ✅ Error messages display for invalid data

### Scenario 3: Warehouse Management
**Objective:** Validate warehouse configuration and management.

**Test Steps:**
1. Navigate to Warehouses section
2. Create new warehouse:
   - Code: WH-TEST
   - Name: Test Warehouse
   - Type: RAW_MATERIALS
   - Location: Test Location
3. Save warehouse configuration
4. Verify warehouse appears in listing
5. Test warehouse type filtering
6. Edit warehouse information
7. Test active/inactive status management

**Expected Results:**
- ✅ Warehouse creation form functions properly
- ✅ Warehouse data saves correctly
- ✅ Type-based filtering works accurately
- ✅ Warehouse editing updates information
- ✅ Status changes reflect immediately

### Scenario 4: Inventory Management and FIFO Operations
**Objective:** Test core inventory functionality with FIFO calculations.

**Test Steps:**
1. Navigate to Inventory section
2. Review existing inventory items
3. Check FIFO batch information display
4. Test inventory filtering options:
   - By warehouse
   - By product
   - By quality status
5. Verify cost calculations are displayed
6. Test search functionality
7. Check critical stock alerts (if any)
8. Review inventory item details

**Expected Results:**
- ✅ Inventory displays with accurate quantities
- ✅ FIFO batch information shows correctly
- ✅ Filtering returns accurate results
- ✅ Cost calculations appear correct
- ✅ Search finds relevant items
- ✅ Critical stock alerts function properly

### Scenario 5: Stock Operations Testing
**Objective:** Validate stock in/out operations with FIFO processing.

**Test Steps:**
1. Navigate to Stock Operations
2. Perform Stock In operation:
   - Select existing product
   - Choose warehouse
   - Enter quantity: 100
   - Enter unit cost: 10.00
   - Select quality status: APPROVED
   - Add entry date and supplier (if available)
3. Submit stock in transaction
4. Verify inventory update
5. Perform Stock Out operation:
   - Select same product and warehouse
   - Enter quantity: 25
   - Add reference information
6. Submit stock out transaction
7. Verify FIFO allocation and cost calculation
8. Check inventory balance update

**Expected Results:**
- ✅ Stock in operation increases inventory
- ✅ Stock out operation decreases inventory correctly
- ✅ FIFO allocation follows chronological order
- ✅ Cost calculations are mathematically accurate
- ✅ Inventory balances update in real-time
- ✅ Transaction history is maintained

### Scenario 6: Dashboard Analytics and Alerts
**Objective:** Test dashboard functionality and critical stock monitoring.

**Test Steps:**
1. Return to Dashboard
2. Review statistics cards:
   - Total Products
   - Active Warehouses
   - Inventory Items
   - Critical Stock Items
3. Check financial overview section
4. Review critical stock alerts (if displayed)
5. Click through dashboard links to detailed views
6. Verify data refresh functionality
7. Test responsive design on different screen sizes

**Expected Results:**
- ✅ Statistics display accurate counts
- ✅ Financial calculations are correct
- ✅ Critical stock alerts show relevant items
- ✅ Dashboard links navigate correctly
- ✅ Data updates reflect recent changes
- ✅ Interface adapts to screen size properly

### Scenario 7: Supplier Management
**Objective:** Test supplier information management.

**Test Steps:**
1. Navigate to Suppliers section
2. Create new supplier:
   - Code: SUPP-001
   - Name: Test Supplier
   - Contact Person: John Doe
   - Email: john@supplier.com
   - Phone: +1-555-0123
3. Save supplier information
4. Test supplier search and filtering
5. Edit supplier details
6. Verify supplier-product associations (if available)

**Expected Results:**
- ✅ Supplier creation saves all information
- ✅ Search finds suppliers accurately
- ✅ Supplier editing updates correctly
- ✅ Contact information displays properly

### Scenario 8: Reports and Analytics
**Objective:** Validate reporting functionality and data accuracy.

**Test Steps:**
1. Navigate to Reports section
2. Review available report types
3. Test date range selection (if available)
4. Generate sample reports
5. Verify data accuracy against known values
6. Test export functionality (if implemented)
7. Check report formatting and readability

**Expected Results:**
- ✅ Reports generate without errors
- ✅ Data matches inventory and transaction records
- ✅ Date filtering works correctly
- ✅ Report formatting is professional
- ✅ Export functions work properly

---

## Feature Validation Checklist

### Authentication and Security ✅
- [ ] Login with valid credentials succeeds
- [ ] Login with invalid credentials fails appropriately
- [ ] Session persistence across browser refresh
- [ ] Automatic logout after token expiry
- [ ] Password field masks input
- [ ] Role-based access control enforced

### User Interface and Experience ✅
- [ ] Responsive design works on mobile devices
- [ ] Navigation is intuitive and consistent
- [ ] Loading states display during data fetching
- [ ] Error messages are clear and helpful
- [ ] Forms validate input before submission
- [ ] Success notifications confirm actions

### Data Management ✅
- [ ] CRUD operations function correctly for all entities
- [ ] Data validation prevents invalid entries
- [ ] Search functionality returns accurate results
- [ ] Filtering options work as expected
- [ ] Pagination handles large datasets
- [ ] Data sorting functions properly

### Inventory Operations ✅
- [ ] Stock in operations increase inventory correctly
- [ ] Stock out operations decrease inventory using FIFO
- [ ] FIFO cost calculations are mathematically accurate
- [ ] Batch tracking maintains entry date order
- [ ] Quality status management functions properly
- [ ] Inventory movements create audit trails

### Business Logic ✅
- [ ] Critical stock alerts trigger at correct levels
- [ ] Cost calculations update automatically
- [ ] Weighted average costs compute correctly
- [ ] Stock availability checks prevent overselling
- [ ] Inventory valuation reflects current costs
- [ ] Business rules are enforced consistently

### Performance and Reliability ✅
- [ ] Page load times are under 3 seconds
- [ ] API responses return within 1 second
- [ ] System handles concurrent users properly
- [ ] Error recovery mechanisms function
- [ ] Data remains consistent during operations
- [ ] System performs well with sample data load

---

## Performance and Usability Testing

### Performance Benchmarks
**Target Performance Metrics:**
- Initial page load: < 3 seconds
- Navigation between pages: < 1 second
- API response time: < 500ms average
- Search results: < 1 second
- Form submission: < 2 seconds

**Testing Procedure:**
1. Use browser developer tools to monitor performance
2. Measure load times for each major page
3. Test with multiple browser tabs open
4. Simulate slow network conditions
5. Test with large datasets (100+ products, inventory items)

### Usability Testing Criteria
**Interface Design:**
- [ ] Clear visual hierarchy and information organization
- [ ] Consistent color scheme and typography
- [ ] Adequate contrast for accessibility
- [ ] Intuitive icon usage and button placement
- [ ] Logical workflow progression

**User Experience:**
- [ ] Minimal clicks required for common tasks
- [ ] Clear feedback for user actions
- [ ] Helpful error messages and recovery options
- [ ] Consistent navigation patterns
- [ ] Mobile-friendly interface design

---

## Business Process Validation

### Inventory Management Process
**Real-World Scenario:** Raw material receipt and usage

1. **Material Receipt:**
   - Supplier delivers 1000 units of raw material
   - Warehouse clerk receives material with quality inspection
   - System records: quantity, cost, supplier, entry date
   - Inventory balance increases correctly

2. **Production Usage:**
   - Production order requires 300 units
   - System allocates oldest inventory first (FIFO)
   - Cost calculation uses FIFO pricing
   - Remaining inventory shows correct balance

3. **Critical Stock Monitoring:**
   - Inventory falls below critical level
   - System displays alert on dashboard
   - Manager receives notification
   - Restocking action can be initiated

### Cost Management Process
**Scenario:** Multiple purchases at different prices

1. Purchase 1: 100 units at $10.00 each (January 1)
2. Purchase 2: 100 units at $12.00 each (January 15)
3. Usage: 150 units for production
4. **Expected FIFO Allocation:**
   - 100 units at $10.00 = $1,000
   - 50 units at $12.00 = $600
   - Total cost: $1,600
   - Weighted average: $10.67 per unit

### Quality Control Process
**Scenario:** Material quality management

1. Incoming material marked as "PENDING" quality status
2. Quality inspection completed
3. Status updated to "APPROVED" or "REJECTED"
4. Only approved materials available for production
5. Rejected materials quarantined automatically

---

## Acceptance Criteria

### Functional Requirements ✅
The system MUST demonstrate:
- [ ] Complete product lifecycle management
- [ ] Accurate FIFO inventory calculations
- [ ] Real-time stock availability tracking
- [ ] Critical stock alert system
- [ ] Comprehensive audit trail for all transactions
- [ ] Role-based user access control
- [ ] Supplier management integration

### Performance Requirements ✅
The system MUST achieve:
- [ ] Sub-3-second page load times
- [ ] Sub-1-second navigation between pages
- [ ] Support for 50+ concurrent users
- [ ] 99%+ uptime during business hours
- [ ] Data backup and recovery capabilities
- [ ] Mobile device compatibility

### Usability Requirements ✅
The system MUST provide:
- [ ] Intuitive interface requiring minimal training
- [ ] Responsive design for all device types
- [ ] Comprehensive error handling and user feedback
- [ ] Accessibility compliance (WCAG 2.1 AA)
- [ ] Consistent design language throughout
- [ ] Context-sensitive help and documentation

### Business Requirements ✅
The system MUST support:
- [ ] Current business workflows without modification
- [ ] Integration with existing processes
- [ ] Scalability for business growth
- [ ] Compliance with industry standards
- [ ] Data security and privacy protection
- [ ] Audit trail for compliance reporting

---

## Issue Reporting Process

### Issue Classification
**Critical Issues (P0):**
- System crashes or becomes unresponsive
- Data loss or corruption
- Security vulnerabilities
- Core business processes fail

**High Priority (P1):**
- Major feature malfunction
- Incorrect calculations or data display
- Performance issues affecting productivity
- Usability problems in primary workflows

**Medium Priority (P2):**
- Minor feature issues
- Cosmetic interface problems
- Non-critical performance concerns
- Enhancement requests

**Low Priority (P3):**
- Documentation issues
- Minor cosmetic improvements
- Nice-to-have features
- Training material updates

### Issue Reporting Template
```
Issue ID: [AUTO-GENERATED]
Date Reported: [YYYY-MM-DD]
Reporter: [NAME AND ROLE]
Priority: [P0/P1/P2/P3]

Title: [BRIEF DESCRIPTION]

Description:
[DETAILED DESCRIPTION OF THE ISSUE]

Steps to Reproduce:
1. [STEP 1]
2. [STEP 2]
3. [STEP 3]

Expected Behavior:
[WHAT SHOULD HAPPEN]

Actual Behavior:
[WHAT ACTUALLY HAPPENS]

Environment:
- Browser: [CHROME/FIREFOX/SAFARI/EDGE]
- Version: [BROWSER VERSION]
- Device: [DESKTOP/TABLET/MOBILE]
- Screen Resolution: [WIDTH x HEIGHT]
- User Account: [TEST ACCOUNT USED]

Screenshots/Videos:
[ATTACH RELEVANT MEDIA]

Additional Notes:
[ANY OTHER RELEVANT INFORMATION]
```

### Issue Resolution Process
1. **Immediate Action:** Critical issues reported immediately to development team
2. **Acknowledgment:** All issues acknowledged within 24 hours
3. **Analysis:** Development team analyzes and estimates resolution time
4. **Resolution:** Issues fixed based on priority and complexity
5. **Verification:** Reporter validates fix before closure
6. **Documentation:** Resolution documented for future reference

---

## Testing Timeline and Milestones

### Phase 1: Initial Testing (Days 1-2)
- [ ] System access and account validation
- [ ] Basic navigation and authentication testing
- [ ] Core feature functionality verification
- [ ] Critical issue identification and reporting

### Phase 2: Comprehensive Testing (Days 3-4)
- [ ] Complete workflow testing
- [ ] Business process validation
- [ ] Performance and usability testing
- [ ] Cross-browser and device testing

### Phase 3: Acceptance Validation (Day 5)
- [ ] Final acceptance criteria verification
- [ ] Issue resolution confirmation
- [ ] Stakeholder sign-off
- [ ] Production readiness assessment

### Success Metrics
- **Functional Testing:** 95%+ test cases pass
- **Performance Testing:** All benchmarks met
- **Usability Testing:** No critical usability issues
- **Business Validation:** All workflows function correctly
- **Stakeholder Approval:** Formal acceptance signed

---

## Final Acceptance Decision

### Acceptance Criteria Summary
For system acceptance, ALL of the following must be achieved:

✅ **Functional Completeness**
- All requested features implemented and working
- Business workflows function end-to-end
- Data accuracy and integrity maintained

✅ **Performance Standards**
- Page load times meet requirements
- System responsive under normal load
- API response times within acceptable limits

✅ **Usability Standards**
- Interface is intuitive and efficient
- Mobile compatibility confirmed
- Error handling provides clear guidance

✅ **Business Value**
- System improves operational efficiency
- Reduces manual work and errors
- Provides accurate business intelligence

### Final Sign-Off
**Stakeholder Approval Required:**
- [ ] Production Planning Manager
- [ ] Inventory Department Head
- [ ] IT Department Representative
- [ ] System Administrator
- [ ] Executive Sponsor

**Approval Statement:**
"I confirm that the Horoz Demir MRP System meets all business requirements and is ready for production deployment."

**Signature:** _________________ **Date:** _________
**Name:** _________________ **Title:** _________

---

**Document Version:** 1.0  
**Prepared By:** Frontend Reporter  
**Review Date:** August 16, 2025  
**File Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/docs/User_Acceptance_Testing_Guide.md`