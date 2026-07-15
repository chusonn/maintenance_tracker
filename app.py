from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key-for-development')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///maintenance_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Flat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flat_number = db.Column(db.String(20), nullable=False)  # Removed unique constraint
    payment_reference = db.Column(db.String(50), unique=True, nullable=False)  # Made this unique
    address = db.Column(db.Text, nullable=False)
    postcode = db.Column(db.String(20))
    tenant_name = db.Column(db.String(100))
    tenant_contact_details = db.Column(db.Text)
    rent_amount = db.Column(db.Float)
    rent_due_date = db.Column(db.Integer)  # Day of month (1-31)
    tenancy_start_date = db.Column(db.Date)
    tenancy_end_date = db.Column(db.Date)
    landlord = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Soft delete fields
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.String(100))  # User who deleted
    
    maintenance_jobs = db.relationship('MaintenanceJob', backref='flat', lazy=True)

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    specialty = db.Column(db.String(100))  # e.g., Plumbing, Electrical, HVAC
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Soft delete fields
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.String(100))  # User who deleted
    
    maintenance_jobs = db.relationship('MaintenanceJob', backref='contractor', lazy=True)

class MaintenanceJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flat_id = db.Column(db.Integer, db.ForeignKey('flat.id'), nullable=False)
    contractor_id = db.Column(db.Integer, db.ForeignKey('contractor.id'), nullable=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='Medium')  # Low, Medium, High, Urgent
    status = db.Column(db.String(20), default='Pending')  # Pending, Scheduled, In Progress, Completed, Cancelled
    
    reported_date = db.Column(db.Date, default=date.today)
    scheduled_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)
    
    estimated_cost = db.Column(db.Float)
    actual_cost = db.Column(db.Float)
    
    notes = db.Column(db.Text)
    follow_up_count = db.Column(db.Integer, default=0)  # Changed from boolean to integer
    follow_up_date = db.Column(db.DateTime)
    follow_up_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Soft delete fields
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    deleted_by = db.Column(db.String(100))  # User who deleted
    
    # Add indexes for better performance
    __table_args__ = (
        db.Index('idx_maintenance_job_status', 'status'),
        db.Index('idx_maintenance_job_priority', 'priority'),
        db.Index('idx_maintenance_job_created_at', 'created_at'),
        db.Index('idx_maintenance_job_flat_id', 'flat_id'),
        db.Index('idx_maintenance_job_contractor_id', 'contractor_id'),
        db.Index('idx_maintenance_job_reported_date', 'reported_date'),
        db.Index('idx_maintenance_job_follow_up_count', 'follow_up_count'),
        db.Index('idx_maintenance_job_is_deleted', 'is_deleted'),
    )

@app.route('/dashboard')
def dashboard():
    # Get statistics (exclude deleted jobs)
    total_jobs = MaintenanceJob.query.filter_by(is_deleted=False).count()
    pending_jobs = MaintenanceJob.query.filter_by(status='Pending', is_deleted=False).count()
    in_progress_jobs = MaintenanceJob.query.filter_by(status='In Progress', is_deleted=False).count()
    completed_jobs = MaintenanceJob.query.filter_by(status='Completed', is_deleted=False).count()
    
    # Get follow-up needed jobs (incomplete jobs with no follow-ups, exclude deleted)
    follow_up_needed = MaintenanceJob.query.filter(
        MaintenanceJob.status.in_(['Pending', 'Scheduled', 'In Progress']),
        MaintenanceJob.follow_up_count == 0,
        MaintenanceJob.is_deleted == False
    ).count()
    
    # Get recent jobs (exclude deleted)
    recent_jobs = MaintenanceJob.query.filter_by(is_deleted=False).order_by(MaintenanceJob.created_at.desc()).limit(10).all()
    
    # Get urgent jobs (exclude deleted)
    urgent_jobs = MaintenanceJob.query.filter_by(priority='Urgent', is_deleted=False).filter(
        MaintenanceJob.status.in_(['Pending', 'In Progress'])
    ).all()
    
    # Get jobs needing follow-up (exclude deleted)
    jobs_needing_followup = MaintenanceJob.query.filter(
        MaintenanceJob.status.in_(['Pending', 'Scheduled', 'In Progress']),
        MaintenanceJob.follow_up_count == 0,
        MaintenanceJob.is_deleted == False
    ).order_by(MaintenanceJob.reported_date.asc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         total_jobs=total_jobs,
                         pending_jobs=pending_jobs,
                         in_progress_jobs=in_progress_jobs,
                         completed_jobs=completed_jobs,
                         follow_up_needed=follow_up_needed,
                         recent_jobs=recent_jobs,
                         urgent_jobs=urgent_jobs,
                         jobs_needing_followup=jobs_needing_followup)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/jobs/<int:job_id>/followup', methods=['GET', 'POST'])
def followup_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    if request.method == 'POST':
        # Increment follow-up count instead of setting boolean
        job.follow_up_count = (job.follow_up_count or 0) + 1
        job.follow_up_date = datetime.utcnow()
        job.follow_up_notes = request.form['follow_up_notes']
        db.session.commit()
        flash(f'Follow-up #{job.follow_up_count} marked as sent!')
        return redirect(url_for('jobs'))
    
    return render_template('followup_job.html', job=job, today_date=date.today())

@app.route('/flats/import', methods=['GET', 'POST'])
def import_flats():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and file.filename.endswith(('.xlsx', '.xls')):
            try:
                import pandas as pd
                df = pd.read_excel(file)
                
                print(f"Excel file loaded. Found {len(df)} rows")
                print(f"Columns: {list(df.columns)}")
                
                imported_count = 0
                updated_count = 0
                skipped_count = 0
                
                for index, row in df.iterrows():
                    # Helper function to clean and convert rent values
                    def clean_rent_value(rent_value):
                        if pd.isna(rent_value) or rent_value == '':
                            return None
                        
                        # Convert to string and clean
                        rent_str = str(rent_value).strip()
                        
                        # Handle multiline values (take the first valid number)
                        if '\n' in rent_str:
                            lines = rent_str.split('\n')
                            for line in lines:
                                cleaned = line.replace(',', '').replace('£', '').replace('$', '').strip()
                                try:
                                    return float(cleaned)
                                except ValueError:
                                    continue
                            return None
                        
                        # Handle single line values
                        cleaned = rent_str.replace(',', '').replace('£', '').replace('$', '').strip()
                        try:
                            return float(cleaned)
                        except ValueError:
                            return None
                    
                    # Helper function to parse UK dates (DD/MM/YYYY)
                    def parse_uk_date(date_value):
                        if pd.isna(date_value) or date_value == '':
                            return None
                        
                        try:
                            date_str = str(date_value).strip()
                            
                            # Handle multiple dates separated by newlines or spaces
                            # Split by newlines first, then by spaces if needed
                            date_parts = []
                            if '\n' in date_str:
                                date_parts = date_str.split('\n')
                            else:
                                # Split by spaces but keep date parts together
                                parts = date_str.split()
                                # Group parts into potential dates (DD/MM/YYYY format)
                                current_date = ''
                                for part in parts:
                                    current_date += part
                                    if '/' in current_date and len(current_date) >= 8:  # DD/MM/YYYY has at least 8 chars
                                        date_parts.append(current_date)
                                        current_date = ''
                                    elif '/' in current_date:
                                        current_date += ' '
                                if current_date.strip():
                                    date_parts.append(current_date.strip())
                            
                            for date_part in date_parts:
                                date_part = date_part.strip()
                                if date_part and '/' in date_part:  # Only process parts that look like dates
                                    try:
                                        return pd.to_datetime(date_part, format='%d/%m/%Y').date()
                                    except:
                                        try:
                                            return pd.to_datetime(date_part, dayfirst=True).date()
                                        except:
                                            continue
                            
                            # If no valid dates found, return None
                            return None
                            
                        except Exception:
                            return None
                    
                    # Helper function to clean and convert due date
                    def clean_due_date(due_date_value):
                        if pd.isna(due_date_value) or due_date_value == '':
                            return None
                        
                        try:
                            # Convert to string and extract first number
                            date_str = str(due_date_value).strip()
                            if '\n' in date_str:
                                date_str = date_str.split('\n')[0].strip()
                            
                            # Extract digits
                            import re
                            numbers = re.findall(r'\d+', date_str)
                            if numbers:
                                day = int(numbers[0])
                                if 1 <= day <= 31:
                                    return day
                        except (ValueError, IndexError):
                            pass
                        
                        return None
                    
                    # Get payment reference (primary identifier)
                    payment_ref = str(row.get('Payment Reference', '')).strip()
                    flat_no = str(row.get('Flat No.', '')).strip()
                    address = str(row.get('Tenancy / Property Address', '')).strip()
                    
                    print(f"Processing row {index + 1}: Payment Ref='{payment_ref}', Flat No='{flat_no}', Address='{address}'")
                    
                    # Skip if no payment reference or address
                    if not payment_ref or not address:
                        print(f"Skipping row {index + 1}: Missing payment reference or address")
                        skipped_count += 1
                        continue
                    
                    # Check if flat already exists by payment reference
                    existing_flat = Flat.query.filter_by(payment_reference=payment_ref).first()
                    
                    if existing_flat:
                        # Update existing flat
                        print(f"Updating existing flat with payment reference: {payment_ref}")
                        existing_flat.flat_number = flat_no if flat_no else existing_flat.flat_number
                        existing_flat.address = address
                        existing_flat.postcode = str(row.get('Tenancy / Property Postcode', '')).strip()
                        existing_flat.tenant_name = str(row.get('Tenants', '')).strip()
                        existing_flat.tenant_contact_details = str(row.get('Tenant Contact Details', '')).strip()
                        existing_flat.rent_amount = clean_rent_value(row.get('Rent', ''))
                        existing_flat.rent_due_date = clean_due_date(row.get('Due Date', ''))
                        existing_flat.landlord = str(row.get('Landlord', '')).strip()
                        
                        # Handle dates using UK format parser
                        if pd.notna(row.get('Tenancy Start Date')):
                            existing_flat.tenancy_start_date = parse_uk_date(row.get('Tenancy Start Date'))
                        if pd.notna(row.get('Tenancy End Date')):
                            existing_flat.tenancy_end_date = parse_uk_date(row.get('Tenancy End Date'))
                        
                        updated_count += 1
                    else:
                        # Create new flat
                        print(f"Creating new flat with payment reference: {payment_ref}")
                        flat = Flat(
                            flat_number=flat_no if flat_no else payment_ref,  # Use payment ref as fallback
                            address=address,
                            postcode=str(row.get('Tenancy / Property Postcode', '')).strip(),
                            tenant_name=str(row.get('Tenants', '')).strip(),
                            tenant_contact_details=str(row.get('Tenant Contact Details', '')).strip(),
                            rent_amount=clean_rent_value(row.get('Rent', '')),
                            rent_due_date=clean_due_date(row.get('Due Date', '')),
                            landlord=str(row.get('Landlord', '')).strip(),
                            payment_reference=payment_ref
                        )
                        
                        # Handle dates using UK format parser
                        if pd.notna(row.get('Tenancy Start Date')):
                            flat.tenancy_start_date = parse_uk_date(row.get('Tenancy Start Date'))
                        if pd.notna(row.get('Tenancy End Date')):
                            flat.tenancy_end_date = parse_uk_date(row.get('Tenancy End Date'))
                        
                        db.session.add(flat)
                        imported_count += 1
                
                db.session.commit()
                flash(f'Successfully imported {imported_count} new flats, updated {updated_count} existing flats, and skipped {skipped_count} empty rows!')
                print(f'Import completed: {imported_count} new, {updated_count} updated, {skipped_count} skipped')
                return redirect(url_for('flats'))
                
            except Exception as e:
                print(f'Import error: {str(e)}')
                import traceback
                traceback.print_exc()
                flash(f'Error importing file: {str(e)}')
                return redirect(url_for('flats'))
        else:
            flash('Invalid file format. Please upload an Excel file (.xlsx or .xls)')
            return redirect(url_for('flats'))
    
    return render_template('import_flats.html')

@app.route('/flats/<int:flat_id>/edit', methods=['GET', 'POST'])
def edit_flat(flat_id):
    flat = Flat.query.get_or_404(flat_id)
    
    if request.method == 'POST':
        flat.flat_number = request.form['flat_number']
        flat.address = request.form['address']
        flat.postcode = request.form['postcode']
        flat.tenant_name = request.form['tenant_name']
        flat.tenant_contact_details = request.form['tenant_contact_details']
        flat.rent_amount = float(request.form['rent_amount']) if request.form['rent_amount'] else None
        flat.rent_due_date = int(request.form['rent_due_date']) if request.form['rent_due_date'] else None
        flat.tenancy_start_date = datetime.strptime(request.form['tenancy_start_date'], '%Y-%m-%d').date() if request.form['tenancy_start_date'] else None
        flat.tenancy_end_date = datetime.strptime(request.form['tenancy_end_date'], '%Y-%m-%d').date() if request.form['tenancy_end_date'] else None
        flat.landlord = request.form['landlord']
        flat.payment_reference = request.form['payment_reference']
        
        db.session.commit()
        flash('Flat updated successfully!')
        return redirect(url_for('flats'))
    
    return render_template('edit_flat.html', flat=flat)

@app.route('/flats/<int:flat_id>/delete', methods=['POST'])
def delete_flat(flat_id):
    flat = Flat.query.get_or_404(flat_id)
    
    # Check if flat has active maintenance jobs
    active_jobs = [job for job in flat.maintenance_jobs if job.status in ['Pending', 'Scheduled', 'In Progress']]
    
    if active_jobs:
        flash(f'Cannot delete flat {flat.flat_number} - it has {len(active_jobs)} active maintenance jobs. Complete or cancel the jobs first.')
        return redirect(url_for('flats'))
    
    try:
        db.session.delete(flat)
        db.session.commit()
        flash(f'Flat {flat.flat_number} ({flat.payment_reference}) deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting flat: {str(e)}')
    
    return redirect(url_for('flats'))

@app.route('/flats/delete-all', methods=['POST'])
def delete_all_flats():
    if request.form.get('confirm') == 'DELETE-ALL-FLATS':
        try:
            # Get count before deletion
            flat_count = Flat.query.count()
            
            # Delete all flats (cascade will delete related maintenance jobs)
            Flat.query.delete()
            db.session.commit()
            
            flash(f'Successfully deleted {flat_count} flats and all related maintenance jobs!')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting all flats: {str(e)}')
    else:
        flash('Deletion cancelled - confirmation phrase was incorrect.')
    
    return redirect(url_for('flats'))

@app.route('/flats')
def flats():
    flats = Flat.query.order_by(Flat.flat_number).all()
    return render_template('flats.html', flats=flats)

@app.route('/flats/add', methods=['GET', 'POST'])
def add_flat():
    if request.method == 'POST':
        flat = Flat(
            flat_number=request.form['flat_number'],
            address=request.form['address'],
            postcode=request.form['postcode'],
            tenant_name=request.form['tenant_name'],
            tenant_contact_details=request.form['tenant_contact_details'],
            rent_amount=float(request.form['rent_amount']) if request.form['rent_amount'] else None,
            rent_due_date=int(request.form['rent_due_date']) if request.form['rent_due_date'] else None,
            tenancy_start_date=datetime.strptime(request.form['tenancy_start_date'], '%Y-%m-%d').date() if request.form['tenancy_start_date'] else None,
            tenancy_end_date=datetime.strptime(request.form['tenancy_end_date'], '%Y-%m-%d').date() if request.form['tenancy_end_date'] else None,
            landlord=request.form['landlord'],
            payment_reference=request.form['payment_reference']
        )
        db.session.add(flat)
        db.session.commit()
        flash('Flat added successfully!')
        return redirect(url_for('flats'))
    return render_template('add_flat.html')

@app.route('/contractors')
def contractors():
    contractors = Contractor.query.filter_by(is_active=True).order_by(Contractor.name).all()
    return render_template('contractors.html', contractors=contractors)

@app.route('/contractors/add', methods=['GET', 'POST'])
def add_contractor():
    if request.method == 'POST':
        contractor = Contractor(
            name=request.form['name'],
            company=request.form['company'],
            email=request.form['email'],
            phone=request.form['phone'],
            specialty=request.form['specialty']
        )
        db.session.add(contractor)
        db.session.commit()
        flash('Contractor added successfully!')
        return redirect(url_for('contractors'))
    return render_template('add_contractor.html')

@app.route('/jobs/export')
def export_jobs():
    # Get all maintenance jobs
    jobs = MaintenanceJob.query.order_by(MaintenanceJob.status, MaintenanceJob.reported_date.desc()).all()
    
    # Prepare data for Excel export
    job_data = []
    for job in jobs:
        job_data.append({
            'Job ID': job.id,
            'Payment Reference': job.flat.payment_reference,
            'Flat Number': job.flat.flat_number or 'No Flat No',
            'Address': job.flat.address,
            'Tenant': job.flat.tenant_name or 'No Tenant',
            'Title': job.title,
            'Description': job.description or '',
            'Priority': job.priority,
            'Status': job.status,
            'Contractor': job.contractor.name if job.contractor else 'Not Assigned',
            'Contractor Email': job.contractor.email if job.contractor and job.contractor.email else '',
            'Reported Date': job.reported_date.strftime('%Y-%m-%d'),
            'Scheduled Date': job.scheduled_date.strftime('%Y-%m-%d') if job.scheduled_date else '',
            'Completed Date': job.completed_date.strftime('%Y-%m-%d') if job.completed_date else '',
            'Notes': job.notes or '',
            'Follow-up Count': job.follow_up_count or 0,
            'Follow-up Date': job.follow_up_date.strftime('%Y-%m-%d') if job.follow_up_date else '',
            'Follow-up Notes': job.follow_up_notes or ''
        })
    
    # Create DataFrame and export to Excel
    import pandas as pd
    from io import BytesIO
    
    df = pd.DataFrame(job_data)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main sheet with all jobs
        df.to_excel(writer, sheet_name='All Jobs', index=False)
        
        # Create separate sheets for each status
        for status in ['Pending', 'Scheduled', 'In Progress', 'Completed', 'Cancelled']:
            status_df = df[df['Status'] == status]
            if not status_df.empty:
                status_df.to_excel(writer, sheet_name=status, index=False)
        
        # Create summary sheet
        summary_data = []
        for status in ['Pending', 'Scheduled', 'In Progress', 'Completed', 'Cancelled']:
            status_count = len(df[df['Status'] == status])
            
            summary_data.append({
                'Status': status,
                'Job Count': status_count,
                'Percentage': (status_count / len(df) * 100) if len(df) > 0 else 0
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    # Prepare file for download
    output.seek(0)
    
    from flask import send_file
    
    # Generate filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'maintenance_jobs_export_{timestamp}.xlsx'
    
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/jobs')
def jobs():
    # Get filter parameters
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    search_query = request.args.get('search', '').strip()
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = request.args.get('page', 1, type=int)
    per_page = 25  # Show 25 jobs per page for better performance
    
    # Build base query with joins for better search performance (exclude deleted)
    query = MaintenanceJob.query.join(Flat).filter(MaintenanceJob.is_deleted == False)
    
    # Apply filters
    if status_filter:
        query = query.filter(MaintenanceJob.status == status_filter)
    if priority_filter:
        query = query.filter(MaintenanceJob.priority == priority_filter)
    
    # Apply search across multiple fields
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                MaintenanceJob.title.ilike(search_pattern),
                MaintenanceJob.description.ilike(search_pattern),
                MaintenanceJob.notes.ilike(search_pattern),
                Flat.payment_reference.ilike(search_pattern),
                Flat.flat_number.ilike(search_pattern),
                Flat.address.ilike(search_pattern)
            )
        )
    
    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(MaintenanceJob.reported_date >= date_from_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(MaintenanceJob.reported_date <= date_to_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    # Order by creation date (newest first) and paginate
    jobs = query.order_by(MaintenanceJob.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get status counts for the cards (from all jobs, not just paginated, exclude deleted)
    all_jobs_query = MaintenanceJob.query.join(Flat).filter(MaintenanceJob.is_deleted == False)
    if status_filter:
        all_jobs_query = all_jobs_query.filter(MaintenanceJob.status == status_filter)
    if priority_filter:
        all_jobs_query = all_jobs_query.filter(MaintenanceJob.priority == priority_filter)
    if search_query:
        search_pattern = f'%{search_query}%'
        all_jobs_query = all_jobs_query.filter(
            db.or_(
                MaintenanceJob.title.ilike(search_pattern),
                MaintenanceJob.description.ilike(search_pattern),
                MaintenanceJob.notes.ilike(search_pattern),
                Flat.payment_reference.ilike(search_pattern),
                Flat.flat_number.ilike(search_pattern),
                Flat.address.ilike(search_pattern)
            )
        )
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            all_jobs_query = all_jobs_query.filter(MaintenanceJob.reported_date >= date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            all_jobs_query = all_jobs_query.filter(MaintenanceJob.reported_date <= date_to_obj)
        except ValueError:
            pass
    
    all_jobs = all_jobs_query.all()
    
    # Calculate status counts
    status_counts = {
        'pending': len([j for j in all_jobs if j.status == 'Pending']),
        'in_progress': len([j for j in all_jobs if j.status == 'In Progress']),
        'completed': len([j for j in all_jobs if j.status == 'Completed']),
        'need_followup': len([j for j in all_jobs if j.follow_up_count == 0 and j.status in ['Pending', 'Scheduled', 'In Progress']])
    }
    
    return render_template('jobs.html', 
                         jobs=jobs, 
                         status_filter=status_filter, 
                         priority_filter=priority_filter,
                         search_query=search_query,
                         date_from=date_from,
                         date_to=date_to,
                         status_counts=status_counts)

@app.route('/jobs/<int:job_id>/delete', methods=['POST'])
def delete_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    try:
        # Soft delete instead of hard delete
        job.is_deleted = True
        job.deleted_at = datetime.utcnow()
        job.deleted_by = "System User"  # You can replace with actual user session
        
        db.session.commit()
        flash('Job moved to recycle bin. You can restore it from the Recycle Bin page.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting job. Please try again.', 'error')
    
    return redirect(url_for('jobs'))

# Recycle Bin Routes
@app.route('/recycle-bin')
def recycle_bin():
    # Get all deleted items
    deleted_jobs = MaintenanceJob.query.filter_by(is_deleted=True).order_by(MaintenanceJob.deleted_at.desc()).all()
    deleted_flats = Flat.query.filter_by(is_deleted=True).order_by(Flat.deleted_at.desc()).all()
    deleted_contractors = Contractor.query.filter_by(is_deleted=True).order_by(Contractor.deleted_at.desc()).all()
    
    return render_template('recycle_bin.html', 
                         deleted_jobs=deleted_jobs,
                         deleted_flats=deleted_flats,
                         deleted_contractors=deleted_contractors)

@app.route('/restore/job/<int:job_id>', methods=['POST'])
def restore_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    try:
        job.is_deleted = False
        job.deleted_at = None
        job.deleted_by = None
        
        db.session.commit()
        flash('Job restored successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error restoring job. Please try again.', 'error')
    
    return redirect(url_for('recycle_bin'))

@app.route('/restore/flat/<int:flat_id>', methods=['POST'])
def restore_flat(flat_id):
    flat = Flat.query.get_or_404(flat_id)
    
    try:
        flat.is_deleted = False
        flat.deleted_at = None
        flat.deleted_by = None
        
        db.session.commit()
        flash('Flat restored successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error restoring flat. Please try again.', 'error')
    
    return redirect(url_for('recycle_bin'))

@app.route('/restore/contractor/<int:contractor_id>', methods=['POST'])
def restore_contractor(contractor_id):
    contractor = Contractor.query.get_or_404(contractor_id)
    
    try:
        contractor.is_deleted = False
        contractor.deleted_at = None
        contractor.deleted_by = None
        
        db.session.commit()
        flash('Contractor restored successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error restoring contractor. Please try again.', 'error')
    
    return redirect(url_for('recycle_bin'))

@app.route('/permanent-delete/job/<int:job_id>', methods=['POST'])
def permanent_delete_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    try:
        db.session.delete(job)
        db.session.commit()
        flash('Job permanently deleted!', 'warning')
    except Exception as e:
        db.session.rollback()
        flash('Error permanently deleting job. Please try again.', 'error')
    
    return redirect(url_for('recycle_bin'))

@app.route('/permanent-delete/flat/<int:flat_id>', methods=['POST'])
def permanent_delete_flat(flat_id):
    flat = Flat.query.get_or_404(flat_id)
    
    try:
        db.session.delete(flat)
        db.session.commit()
        flash('Flat permanently deleted!', 'warning')
    except Exception as e:
        db.session.rollback()
        flash('Error permanently deleting flat. Please try again.', 'error')
    
    return redirect(url_for('recycle_bin'))

@app.route('/permanent-delete/contractor/<int:contractor_id>', methods=['POST'])
def permanent_delete_contractor(contractor_id):
    contractor = Contractor.query.get_or_404(contractor_id)
    
    try:
        db.session.delete(contractor)
        db.session.commit()
        flash('Contractor permanently deleted!', 'warning')
    except Exception as e:
        db.session.rollback()
        flash('Error permanently deleting contractor. Please try again.', 'error')
    
    return redirect(url_for('recycle_bin'))

@app.route('/jobs/add', methods=['GET', 'POST'])
def add_job():
    if request.method == 'POST':
        try:
            # Safely convert estimated_cost to float
            estimated_cost = request.form['estimated_cost']
            estimated_cost = float(estimated_cost) if estimated_cost and estimated_cost.strip() else None
        except (ValueError, TypeError):
            estimated_cost = None
            flash('Estimated cost must be a valid number. It has been set to empty.', 'warning')
        
        job = MaintenanceJob(
            flat_id=request.form['flat_id'],
            title=request.form['title'],
            description=request.form['description'],
            priority=request.form['priority'],
            estimated_cost=estimated_cost,
            reported_date=datetime.now()
        )
        db.session.add(job)
        db.session.commit()
        flash('Job added successfully!')
        return redirect(url_for('jobs'))
    
    flats = Flat.query.order_by(Flat.payment_reference).all()
    return render_template('add_job.html', flats=flats)

@app.route('/jobs/<int:job_id>/schedule', methods=['GET', 'POST'])
def schedule_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    if request.method == 'POST':
        job.contractor_id = request.form['contractor_id']
        job.scheduled_date = datetime.strptime(request.form['scheduled_date'], '%Y-%m-%d').date()
        job.status = 'Scheduled'
        job.notes = request.form['notes']
        db.session.commit()
        flash('Job scheduled successfully!')
        return redirect(url_for('jobs'))
    
    contractors = Contractor.query.filter_by(is_active=True).order_by(Contractor.name).all()
    return render_template('schedule_job.html', job=job, contractors=contractors)

@app.route('/jobs/<int:job_id>/complete', methods=['GET', 'POST'])
def complete_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    if request.method == 'POST':
        try:
            # Safely convert actual_cost to float
            actual_cost = request.form['actual_cost']
            actual_cost = float(actual_cost) if actual_cost and actual_cost.strip() else None
        except (ValueError, TypeError):
            actual_cost = None
            flash('Actual cost must be a valid number. It has been set to empty.', 'warning')
        
        job.status = 'Completed'
        job.completed_date = date.today()
        job.actual_cost = actual_cost
        job.notes = request.form['notes']
        db.session.commit()
        flash('Job marked as completed!')
        return redirect(url_for('jobs'))
    
    return render_template('complete_job.html', job=job, today_date=date.today().strftime('%Y-%m-%d'))

@app.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
def edit_job(job_id):
    job = MaintenanceJob.query.get_or_404(job_id)
    
    if request.method == 'POST':
        try:
            # Safely convert estimated_cost to float
            estimated_cost = request.form['estimated_cost']
            estimated_cost = float(estimated_cost) if estimated_cost and estimated_cost.strip() else None
        except (ValueError, TypeError):
            estimated_cost = None
            flash('Estimated cost must be a valid number. It has been set to empty.', 'warning')
        
        job.title = request.form['title']
        job.description = request.form['description']
        job.priority = request.form['priority']
        job.status = request.form['status']
        job.estimated_cost = estimated_cost
        job.notes = request.form['notes']
        db.session.commit()
        flash('Job updated successfully!')
        return redirect(url_for('jobs'))
    
    flats = Flat.query.order_by(Flat.payment_reference).all()
    return render_template('edit_job.html', job=job, flats=flats)

if __name__ == '__main__':
    with app.app_context():
        # Run migrations before starting app
        from migrate import migrate_database
        
        print("🔄 Checking database migrations...")
        migration_needed = migrate_database()
        
        if migration_needed:
            print("✅ Database migrated successfully!")
        else:
            print("✅ Database is up to date!")
        
        # Create tables if they don't exist
        db.create_all()
        print("✅ Database tables ready!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
