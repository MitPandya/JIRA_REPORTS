from prettytable import PrettyTable
import re
import sqlite3


def get_db_data_as_dict(table_name):
	try:
		conn = sqlite3.connect('jira_reports.db')
		if conn == None:
			print "error fetching data from db!"
			return
		c = conn.cursor()
		c.execute('SELECT * from '+table_name)
		data = c.fetchall()
	except sqlite3.Error as e:
		print("An error occurred while fetching data from db ", e.args[0])

	if conn != None:
		conn.close()

	if len(data) > 0:
		return data
	return None

def create_table_columns(data):
	cols = ['JIRA_ID']
	for k,v in data.items():
		dic = dict(eval(v))
		for key,value in dic.items():
			if not key in cols:
				cols.append(key)
	return cols


def print_table(cols,data):
	x = PrettyTable(cols)
	m = re.compile(r'\b[0-9a-f]{5,40}\b')
	for k,v in data.items():
		dic = dict(eval(v))
		row = [k]
		for col in cols[1:]:
			temp = m.findall(str(dic[col])) if col in dic else '-'
			if temp == '-':
				row.append(temp)
			else:
				if len(temp) == 0:
					row.append('Needs merge')
				else:
					row.append(temp[0])
		x.add_row(row)

	print x


if __name__ == '__main__':
	data = get_db_data_as_dict('branch_with_partial_commits')
	if data == None:
		print "No data to print"
		exit(1)
	data = dict(data)
	cols = create_table_columns(data)
	print_table(cols, data)
