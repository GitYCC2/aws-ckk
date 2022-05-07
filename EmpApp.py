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

    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM employee")
    data =  cursor.fetchall()
    contents = show_image(bucket)
    emp_data = np.column_stack((contents, data))
    return render_template('index.html', emp_data = emp_data)

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
        
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM employee")
    data =  cursor.fetchall()
    contents = show_image(bucket)
    emp_data = np.column_stack((contents, data))
    return render_template('index.html', emp_data = emp_data)

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
    cursor.execute("SELECT e.emp_id, e.first_name, e.last_name FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id WHERE a.emp_id IS NULL")
    checkin_data =  cursor.fetchall()

    # Get employee who has checked in but haven't checkout
    cursor.execute("SELECT e.emp_id, e.first_name, e.last_name FROM employee e LEFT JOIN attendance a ON e.emp_id = a.emp_id WHERE a.checkout_time IS NULL AND a.emp_id IS NOT NULL")
    checkout_data =  cursor.fetchall()
    
    return render_template('Attendance.html', checkin_data = checkin_data, checkout_data = checkout_data)

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
    
    return redirect(url_for('/attendance'))
  
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
    
    return redirect(url_for('/attendance'))    
    

@app.route("/about", methods=['POST'])
def about():
    return render_template('www.intellipaat.com')

@app.route("/getemp", methods=['POST'])
def GetEmp():
    return render_template('GetEmp.html')

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
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM employee")
    data =  cursor.fetchall()
    contents = show_image(bucket)
    emp_data = np.column_stack((contents, data))
    return render_template('index.html', emp_data = emp_data)


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
