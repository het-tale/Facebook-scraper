from flask import Flask, redirect, url_for, render_template, request, session, Response
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import requests
from bs4 import BeautifulSoup
import io
import csv
from tqdm import tqdm 
from lxml import html
import pandas as pd
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException
#added
from datetime import date

app = Flask(__name__)

app.secret_key = 'ensab'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'scrapit'
mysql = MySQL(app)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ''
    # Check if "username", "password" and "email" POST requests exist (user submitted form)
    if request.method == 'POST' and 'password' in request.form and 'email' in request.form:
        # Create variables for easy access
        password = request.form['password']
        email = request.form['email']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM login WHERE email = %s', (email,))
        account = cursor.fetchone()
        # If account exists show error and validation checks
        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
        elif not password or not email:
            msg = 'Please fill out the form!'
        else:
            # Account doesnt exists and the form data is valid, now insert new account into accounts table
            cursor.execute('INSERT INTO login VALUES (NULL, %s, %s)', (email, password))
            mysql.connection.commit()
            msg = 'You have successfully registered!'
    elif request.method == 'POST':
        # Form is empty... (no POST data)
        msg = 'Please fill out the form!'
    # Show registration form with message (if any)
    return render_template('register.html', msg=msg)

@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM login WHERE email = %s AND password = %s', (email, password))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['email'] = account['email']
            # Redirect to home page
            return redirect(url_for('welcome'))
        else:
            msg = 'Incorrect username/password!'
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Remove session data, this will log the user out
   session.pop('loggedin', None)
   session.pop('id', None)
   session.pop('email', None)
   # Redirect to login page
   return redirect(url_for('home'))

@app.route("/index")
def welcome():
    if 'loggedin' in session:
        # User is loggedin show them the home page
        return render_template("welcome.html")
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))
@app.route("/extract")
def extract():
    if 'loggedin' in session:
        # User is loggedin show them the home page
        return render_template("scrap.html")
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))
@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    if 'loggedin' in session:
        options = Options()
        options.headless = True
        browser = webdriver.Firefox(options=options)
        browser.implicitly_wait(5)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("USE scrapit")
        browser.get('https://mbasic.facebook.com/')

        sleep(2)


        username_input = browser.find_element_by_css_selector("input[name='email']")

        password_input = browser.find_element_by_css_selector("input[name='pass']")
        

        username_input.send_keys("username")

        password_input.send_keys("password")

        sleep(2)
        login_button = browser.find_element_by_css_selector("input[type='submit']")

        login_button.click()
        ok_button = browser.find_element_by_css_selector("input[type='submit'").click()
        sleep(5)
        post_url = request.form.get("url")
        cursor.execute('SELECT * FROM post WHERE post_url = %s', (post_url,))
        post = cursor.fetchone()
        if not post:
            cursor.execute('INSERT INTO post VALUES (NULL, %s)', (post_url,))
            mysql.connection.commit()
        if post_url == "":
            browser.close()
        browser.get(post_url)
        browser.find_element_by_xpath("//a[contains(@href,'reaction/profile')]").click() #click the reaction number
        count = 0
        while(True):
            tree = html.fromstring(browser.page_source)
            table_xpath = "//table//li/table/tbody/tr/td[@class]/table/tbody/tr"
            user = tree.xpath(table_xpath+"/td[3]//a/text()")
            user_url = tree.xpath(table_xpath+"/td[3]//a/@href")
            users_number = len(user)
            for i in range(users_number):
                cursor.execute('INSERT INTO users VALUES (NULL, %s, NULL, %s, %s)', (user[i], user_url[i], post_url))
                mysql.connection.commit()

            next_link = tree.xpath('//span[contains(text() ,"See more")]/parent::a/@href') #find see more
        
            if len(next_link)!= 0:
                browser.find_element_by_xpath('//span[contains(text() ,"See more")]/parent::a').click()
                count += 1
                if count > 400:
                    next_link = ''
                    break
            else:
                next_link = ''
                break
        sleep(2)
        cursor.execute("SELECT * FROM users WHERE post_url = %s", (post_url,))
        data = cursor.fetchall()
        number_users = len(data)
        print(number_users)
        if number_users < 10:
            for row in data:
                url1 = ''
                if row["user_url"].find("profile.php") != -1:
                    url1 = "https://m.facebook.com/"+row["user_url"]+"&v=info"
                else:
                    url1 = "https://m.facebook.com/"+row["user_url"]+"/about"
                browser.get(url1)
                try:
                    basic_info = browser.find_element_by_id("basic-info")
                    info = basic_info.find_elements_by_class_name("_5cds")
                    info_number = len(info)
                    if info_number < 2:
                        gender_value = basic_info.find_elements_by_class_name("_5cdv")[0].text
                        if gender_value != "Female" and gender_value != "Male":
                            gender_value = "None"
                    else:
                        birth_value = basic_info.find_elements_by_class_name("_52ja")[1].text
                        if birth_value == "Date of birth":
                            gender = basic_info.find_elements_by_class_name("_52ja")[3].text
                            if gender == "Gender":
                                gender_value = basic_info.find_elements_by_class_name("_5cdv")[1].text
                            else:
                                gender_value = "None"
                        else:
                            gender = birth_value
                            if gender == "Gender":
                                gender_value = basic_info.find_elements_by_class_name("_5cdv")[0].text
                            else:
                                gender_value = "None"

                except:
                    gender_value = "None"
                finally:
                    print(gender_value)
                    cursor.execute('UPDATE users SET gender = %s WHERE user_url = %s', (gender_value,row["user_url"]))
                    mysql.connection.commit()
        browser.close()
        return render_template("scrap.html")
    return redirect(url_for('login'))
@app.route("/export")
def export():
    if 'loggedin' in session:
        cursor = None
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("USE scrapit")
            
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            line = ['Id, Name, URL, Post URL']
            writer.writerow(line)
            
            for row in result:
                line = [str(row['id']) + ',' + row['user'] + ',' + row['user_url'] + ',' + row['post_url']]
                writer.writerow(line)
            
            output.seek(0)
            
            return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=users.csv"})
        except Exception as e:
            print(e)
        finally:
            cursor.close()
    return redirect(url_for('login'))

@app.route("/message")
def message():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('USE scrapit')
        cursor.execute("SELECT * FROM post")
        data1 = cursor.fetchall()
        return render_template("message.html", data = data1)
    return redirect(url_for('login'))

@app.route("/automate", methods=["GET", "POST"])
def automate():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('USE scrapit')
        options = Options()
        options.headless = True
        browser = webdriver.Firefox(options=options)
        browser.implicitly_wait(5)

        browser.get('https://mbasic.facebook.com/')

        sleep(2)


        username_input = browser.find_element_by_css_selector("input[name='email']")

        password_input = browser.find_element_by_css_selector("input[name='pass']")
        
        #username
        username_input.send_keys("username")

        password_input.send_keys("password")

        sleep(2)
        login_button = browser.find_element_by_css_selector("input[type='submit']")

        login_button.click()
        ok_button = browser.find_element_by_css_selector("input[type='submit'").click()
        sleep(5)

        post_url = request.form.get("post_url")
        gender = request.form.get("gender")
        cursor.execute("SELECT * FROM users WHERE post_url = %s AND gender = %s", (post_url,gender))
        data = cursor.fetchall()
        msg = request.form.get("message")
        url1 = ''
        for row in data:
            url = row["user_url"]
            url1 = "https://mbasic.facebook.com/"+url
            browser.get(url1)
            #-------------------------------------------------------------Profile-------------------------------------------------------
            try:
                msg_btn = browser.find_element_by_xpath("//*[text() = 'Message']").click()
                #already ran a conversation
                try:
                    msg_area = browser.find_element_by_id("composerInput")
                    msg_area.send_keys(msg)
                    send_msg = browser.find_element_by_css_selector("input[name='send']").click()
                    sleep(3)
                    #msg for first time
                except:
                    msg_area = browser.find_element_by_xpath("/html/body/div/div/div[2]/div/table/tbody/tr/td/div/form/div[2]/table/tbody/tr/td[1]/textarea")
                    msg_area.send_keys(msg)
                    send_msg = browser.find_element_by_css_selector("input[name='Send']").click()
                    sleep(3)
            #-----------------------------------------Page-------------------------------------------------
            except NoSuchElementException:
                pass
            except:
                msg_btn = browser.find_element_by_xpath("/html/body/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/table/tbody/tr/td[3]/a").click()
                #msg for first time
                try:
                    msg_area = browser.find_element_by_xpath("/html/body/div/div/div[2]/div/table/tbody/tr/td/div/form/div[2]/table/tbody/tr/td[1]/textarea")
                    msg_area.send_keys(msg)
                    send_msg = browser.find_element_by_css_selector("input[name='Send']").click()
                    sleep(3)
                #already ran a conversation
                except:
                    msg_area = browser.find_element_by_id("composerInput")
                    msg_area.send_keys(msg)
                    send_msg = browser.find_element_by_css_selector("input[name='send']").click()
                    sleep(3)
        #added
        today = date.today()
        dt_string = today.strftime("%d/%m/%Y")
        cursor.execute("INSERT INTO message VALUES(NULL,%s,%s)", (dt_string,msg))
        mysql.connection.commit()
        browser.close()
        return render_template("message.html")
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)