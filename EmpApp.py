from flask import Flask, render_template, request, redirect, url_for
from pymysql import connections
import os
import boto3
import numpy as np
from config import *

app = Flask(__name__)

bucket = custombucket
region = customregion

db_conn = connections.Connection(
    host=customhost,
    port=3306,
    user=customuser,
    password=custompass,
    db=customdb

)
output = {}
table = 'employee'

def show_image(bucket):
    s3_client = boto3.client('s3')
    public_urls = []
    try:
        for item in s3_client.list_objects(Bucket=bucket)['Contents']:
            presigned_url = s3_client.generate_presigned_url('get_object', Params = {'Bucket': bucket, 'Key': item['Key']}, ExpiresIn = 100)
            public_urls.append(presigned_url)
    except Exception as e:
        pass
    # print("[INFO] : The contents inside show_image = ", public_urls)
    return public_urls

@app.route("/addemp", methods=['POST'])
def AddEmp():
    emp_id = request.form['emp_id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    pri_skill = request.form['pri_skill']
    location = request.form['location']
    emp_image_file = request.files['emp_image_file']

    insert_sql = "INSERT INTO employee VALUES (%s, %s, %s, %s, %s)"
    cursor = db_conn.cursor()

    if emp_image_file.filename == "":
        return "Please select a file"

    try:

        cursor.execute(insert_sql, (emp_id, first_name, last_name, pri_skill, location))
        db_conn.commit()
        emp_name = "" + first_name + " " + last_name
        # Uplaod image file in S3 #
        emp_image_file_name_in_s3 = "emp-id-" + str(emp_id) + "_image_file"
        s3 = boto3.resource('s3')

        try:
            print("Data inserted in MySQL RDS... uploading image to S3...")
            s3.Bucket(custombucket).put_object(Key=emp_image_file_name_in_s3, Body=emp_image_file)
            bucket_location = boto3.client('s3').get_bucket_location(Bucket=custombucket)
            s3_location = (bucket_location['LocationConstraint'])

            if s3_location is None:
                s3_location = ''
            else:
                s3_location = '-' + s3_location

            object_url = "https://s3{0}.amazonaws.com/{1}/{2}".format(
                s3_location,
                custombucket,
                emp_image_file_name_in_s3)

        except Exception as e:
            return str(e)

    finally:
        cursor.close()

    print("all modification done...")
    
    return redirect(url_for('home'))

@app.route("/manageemp", methods=['POST'])
def ManageEmp():
    if request.form['submitBtn'] == 'deleteBtn':
        emp_id = request.form['emp_id']
        #emp_file = request.form['emp_file']
        temp_file = request.form['emp_file'].split('/')
        split_file = temp_file[3].split('?')
        emp_file = split_file[0]

        cursor = db_conn.cursor()
        try: 
            s3 = boto3.resource('s3')
            s3.Object(bucket, emp_file).delete()

            sql = "DELETE FROM employee WHERE emp_id = %s"
            delete_emp = (emp_id,)
            cursor.execute(sql, delete_emp)
            db_conn.commit()
            cursor.close()
        except Exception as e:
            return str(e)
    elif request.form['submitBtn'] == 'editBtn':
        emp_id = request.form['emp_id']
        emp_file = request.form['emp_file']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        pri_skill = request.form['pri_skill']
        location = request.form['location']
        
        row = [emp_file, emp_id, first_name, last_name, pri_skill, location]
        return render_template('EditEmp.html', row = row) 

    return redirect(url_for('home'))

@app.route("/editemp", methods=['POST'])
def EditEmp():
    emp_id = request.form['emp_id'] 
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    pri_skill = request.form['pri_skill']
    location = request.form['location']
    emp_image_file = request.files['emp_image_file']
    
    update_sql = "UPDATE employee SET first_name=%s, last_name=%s, pri_skill=%s, location=%s WHERE emp_id=%s"
    cursor = db_conn.cursor()

    try:
        cursor.execute(update_sql, (first_name, last_name, pri_skill, location, emp_id))
        db_conn.commit()
        
        try:
            if emp_image_file.filename is not "":
                #emp_name = "" + first_name + " " + last_name
                # Uplaod image file in S3 #
                emp_image_file_name_in_s3 = "emp-id-" + str(emp_id) + "_image_file"
                s3 = boto3.resource('s3')
                
                print("Data inserted in MySQL RDS... uploading image to S3...")
                s3.Bucket(custombucket).put_object(Key=emp_image_file_name_in_s3, Body=emp_image_file)
                bucket_location = boto3.client('s3').get_bucket_location(Bucket=custombucket)
                s3_location = (bucket_location['LocationConstraint'])

                if s3_location is None:
                    s3_location = ''
                else:
                    s3_location = '-' + s3_location

                object_url = "https://s3{0}.amazonaws.com/{1}/{2}".format(
                    s3_location,
                    custombucket,
                    emp_image_file_name_in_s3)

        except Exception as e:
            return str(e)

    finally:
        cursor.close()
        
    return redirect(url_for('home'))

@app.route("/", methods=['GET', 'POST'])
def home():
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM employee")
    data =  cursor.fetchall()
    contents = show_image(bucket)
    emp_data = np.column_stack((contents, data))
    return render_template('index.html', emp_data = emp_data)

@app.route("/goaddemp")
def AddEmpPage():
    return render_template('AddEmp.html')

@app.route("/attendance")
def AttendancePage():
    cursor = db_conn.cursor()
    
    # Get employee who hasn't checked in 
    cursor.execute("SELECT emp_id, first_name, last_name FROM employee WHERE emp_id NOT IN (SELECT distinct(e.emp_id) FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id WHERE a.checkin_time IS NOT NULL AND a.checkout_date IS NULL)")
    checkin_data =  cursor.fetchall()

    # Get employee who has checked in but haven't checkout
    cursor.execute("SELECT e.emp_id, e.first_name, e.last_name FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id WHERE a.checkout_time IS NULL AND a.emp_id IS NOT NULL")
    checkout_data =  cursor.fetchall()
    
    # Get employee attendance record
    cursor.execute("SELECT e.emp_id, e.first_name, e.last_name, a.checkin_time, a.checkin_date, a.checkout_time, a.checkout_date FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id WHERE a.emp_id IS NOT NULL")
    attendance_data = cursor.fetchall()
    
    return render_template('Attendance.html', checkin_data = checkin_data, checkout_data = checkout_data, attendance_data = attendance_data)

@app.route("/checkin", methods=['POST'])
def CheckIn():
    emp_id = request.form['emp_id']
    checkin_time = request.form['checkin_time']
    checkin_date = request.form['checkin_date']
    insert_sql = "INSERT INTO attendance (checkin_time, checkin_date, emp_id) VALUES (%s, %s, %s)"
    cursor = db_conn.cursor()
    cursor.execute(insert_sql, (checkin_time, checkin_date, emp_id))
    db_conn.commit()
    cursor.close()
    
    return redirect(url_for('AttendancePage'))
  
@app.route("/checkout", methods=['POST'])
def CheckOut():
    emp_id = request.form['emp_id']
    checkout_time = request.form['checkout_time']
    checkout_date = request.form['checkout_date']
    update_sql = "UPDATE attendance SET checkout_time=%s, checkout_date=%s WHERE emp_id=%s AND checkout_time IS NULL"
    cursor = db_conn.cursor()
    cursor.execute(update_sql, (checkout_time, checkout_date, emp_id))
    db_conn.commit()
    cursor.close()
    
    return redirect(url_for('AttendancePage'))  

@app.route("/leave")
def LeavePage():
    cursor = db_conn.cursor()
    cursor.execute("SELECT e.emp_id, e.first_name, e.last_name, l.start_date, l.end_date, l.reason, l.status, l.leave_id FROM employee e LEFT JOIN emp_leave l ON e.emp_id = l.emp_id WHERE l.start_date IS NOT NULL")
    leave_data = cursor.fetchall()
    
    return render_template('Leave.html', leave_data = leave_data)

@app.route("/addleavepage")
def AddLeavePage():
    cursor = db_conn.cursor()
    cursor.execute("SELECT emp_id, first_name, last_name FROM employee")
    emp = cursor.fetchall()
    
    return render_template('AddLeave.html', emp = emp)

@app.route("/addleave", methods=['POST'])
def AddLeave():
    emp_id = request.form['emp_id']
    start_date = request.form['startdate']
    end_date = request.form['enddate']
    reason = request.form['reason']
    status = 'Requested'
    
    insert_sql = "INSERT INTO emp_leave (start_date, end_date, reason, status, emp_id) VALUES (%s, %s, %s, %s, %s)"
    cursor = db_conn.cursor()
    cursor.execute(insert_sql, (start_date, end_date, reason, status, emp_id))
    db_conn.commit()
    cursor.close()
    
    return redirect(url_for('LeavePage'))

@app.route("/updateleavepage", methods=['POST'])
def UpdateLeavePage():
    leave_id = request.form['leave_id']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    reason = request.form['reason']
    status = request.form['status']
    emp_id = request.form['emp_id']
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT emp_id, first_name, last_name FROM employee")
    emp = cursor.fetchall()
    
    get_emp = [emp_id, start_date, end_date, reason, status, leave_id]
    
    return render_template('EditLeave.html', get_emp = get_emp, emp = emp)
    
@app.route("/updateleave", methods=['POST'])
def UpdateLeave():
    leave_id = request.form['leave_id']
    start_date = request.form['startdate']
    end_date = request.form['enddate']
    reason = request.form['reason']
    status = request.form['status']
    
    update_sql = "UPDATE emp_leave SET start_date=%s, end_date=%s, reason=%s, status=%s WHERE leave_id=%s"
    cursor = db_conn.cursor()
    cursor.execute(update_sql, (start_date, end_date, reason, status, leave_id))
    db_conn.commit()
    cursor.close()
    
    return redirect(url_for('LeavePage'))
    

@app.route("/payroll")
def PayrollPage():
    cursor = db_conn.cursor()
    cursor.execute("SELECT emp_id, first_name, last_name FROM employee")
    emp = cursor.fetchall()
      
    cursor.execute("SELECT e.emp_id, e.first_name, e.last_name, p.pay_date, p.total, p.until, p.benefits FROM employee e LEFT JOIN payroll p ON e.emp_id = p.emp_id WHERE p.pay_date IS NOT NULL");
    payroll = cursor.fetchall()
    
    return render_template('Payroll.html', emp = emp, payroll = payroll)
    
@app.route("/emppay", methods=['POST'])
def AddPayrollPage():
    emp_id = request.form['emp_id']
    cursor = db_conn.cursor()
    select_sql = "SELECT checkout_date FROM attendance WHERE emp_id=%s ORDER BY checkout_date DESC LIMIT 1"
    cursor = db_conn.cursor()
    cursor.execute(select_sql, (emp_id))
    checkout_date = cursor.fetchone()
    
    select_sql2 = "SELECT pay_date FROM payroll WHERE emp_id=%s ORDER BY pay_date DESC LIMIT 1"
    cursor = db_conn.cursor()
    cursor.execute(select_sql2, (emp_id))
    pay_date = cursor.fetchone()
    
    if not pay_date:
        select_sql3 = "SELECT e.pri_skill, SUM(HOUR(a.checkout_time)), e.first_name, e.last_name FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id WHERE a.checkout_date <= %s AND a.emp_id = %s"
        cursor = db_conn.cursor()
        cursor.execute(select_sql3, (checkout_date, emp_id))
    else:
        select_sql3 = "SELECT e.pri_skill, SUM(HOUR(a.checkout_time)), e.first_name, e.last_name FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id LEFT JOIN payroll p ON p.emp_id = e.emp_ID WHERE p.pay_date > %s AND a.checkout_date <= %s AND a.emp_id = %s"
        cursor = db_conn.cursor()
        cursor.execute(select_sql3, (pay_date, checkout_date, emp_id))

    result = cursor.fetchone()
    
    if result[0] == "Project Manager":
        total = 100 * result[1]
    elif result[0] == "Cloud Architect":
        total = 50 * result[1]
    elif result[0] == "Web Developer":
        total = 45 * result[1]
    elif result[0] == "Network Administrator":
        total = 55 * result[1]
    elif result[0] == "IT Support":
        total = 30 * result[1]
    
    first_name = result[2]
    last_name = result[3]
    hour = result[1]
    
    row = [emp_id, first_name, last_name, checkout_date, total, hour]
    
    return render_template('AddPayroll.html', row = row)

@app.route("/about", methods=['POST'])
def about():
    return render_template('www.intellipaat.com')

@app.route("/getemp", methods=['POST'])
def GetEmp():
    return render_template('GetEmp.html')

@app.route("/editemp")
def GetEmpData():
    id = request.form['emp_id']
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM employee where emp_id = %s", (id))
    data = cursor.fetchall()
    
    return render_template('GetEmp.html', data = data)

@app.route("/fetchdata", methods=['GET'])
def GoBackHome():
    return render_template('AddEmp.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
