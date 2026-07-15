# Maintenance Tracker System

A comprehensive web-based maintenance tracking system designed for property management companies and maintenance virtual assistants. This system helps streamline the process of scheduling contractors, tracking maintenance jobs, and managing property information.

## Features

### 🏠 **Property Management**
- Add and manage multiple flats/properties
- Store tenant contact information
- Track active maintenance jobs per property

### 👷 **Contractor Management**
- Maintain a database of contractors with specialties
- Track contractor availability and active jobs
- Store contact information and company details

### 📋 **Job Tracking**
- Create maintenance requests with priority levels
- Schedule jobs with assigned contractors
- Track job status from pending to completion
- Record estimated vs actual costs
- Add detailed notes and descriptions

### 📊 **Dashboard Overview**
- Real-time statistics on job status
- Urgent job alerts
- Recent activity feed
- Quick access to common actions

### 🎯 **Priority Management**
- Four priority levels: Low, Medium, High, Urgent
- Color-coded visual indicators
- Priority-based filtering and sorting

## Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Setup Instructions

1. **Clone or download the project** to your local directory

2. **Navigate to the project directory:**
   ```bash
   cd maintenance_tracker
   ```

3. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

4. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Open your web browser** and navigate to:
   ```
   http://localhost:5000
   ```

## Getting Started

### 1. Add Your Properties
- Navigate to the "Flats" section
- Click "Add New Flat"
- Enter property details and tenant information

### 2. Add Contractors
- Go to the "Contractors" section
- Click "Add New Contractor"
- Enter contractor details and specialties

### 3. Create Your First Job
- Navigate to "Jobs" and click "Add New Job"
- Select the property, describe the issue, and set priority
- Schedule the job with an appropriate contractor

### 4. Track Progress
- Use the dashboard to monitor job status
- Update job details as work progresses
- Mark jobs as completed when finished

## System Structure

### Database Tables
- **Flats**: Property information and tenant details
- **Contractors**: Contractor information and specialties
- **Maintenance Jobs**: Job details, scheduling, and status tracking

### Key Features
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Instant status changes and notifications
- **Cost Tracking**: Monitor estimated vs actual costs
- **Filtering & Sorting**: Find jobs quickly with advanced filters
- **Priority Management**: Visual indicators for urgent tasks

## Usage Tips

### For Maintenance Virtual Assistants
1. **Start with urgent jobs** - Check the dashboard daily for urgent items
2. **Keep contractor info updated** - Regular contact information checks
3. **Use detailed descriptions** - Help contractors understand the work needed
4. **Track costs carefully** - Compare estimates with actual costs
5. **Follow up promptly** - Use the notes system to track communications

### Best Practices
- Set appropriate priority levels for accurate triage
- Schedule jobs based on contractor specialties
- Keep tenant contact information current
- Document completion details for future reference
- Review cost comparisons for budget planning

## Technical Details

### Technologies Used
- **Backend**: Flask (Python web framework)
- **Database**: SQLite (included)
- **Frontend**: Bootstrap 5, HTML5, JavaScript
- **Icons**: Font Awesome

### File Structure
```
maintenance_tracker/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── maintenance_tracker.db # SQLite database (created automatically)
├── templates/            # HTML templates
│   ├── base.html         # Base template with navigation
│   ├── dashboard.html   # Main dashboard view
│   ├── jobs.html         # Job listing and management
│   ├── add_job.html      # Create new job form
│   ├── edit_job.html     # Edit existing job
│   ├── schedule_job.html # Schedule job with contractor
│   ├── complete_job.html # Mark job as completed
│   ├── flats.html        # Property listing
│   ├── add_flat.html     # Add new property
│   ├── contractors.html  # Contractor listing
│   └── add_contractor.html # Add new contractor
└── README.md            # This file
```

## Support

This system is designed to be intuitive and user-friendly. If you encounter any issues:

1. **Database Issues**: Delete `maintenance_tracker.db` and restart the application
2. **Port Conflicts**: The application uses port 5000 by default
3. **Performance**: The system is optimized for managing up to 1000+ properties

## Future Enhancements

Potential features for future versions:
- Email notifications for tenants and contractors
- Automated follow-up reminders
- Advanced reporting and analytics
- Mobile app companion
- Integration with calendar systems
- Photo attachments for job documentation
- Contractor rating system

---

**Maintenance Tracker** - Streamlining property maintenance management for virtual assistants and property managers.
