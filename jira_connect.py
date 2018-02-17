from jira import JIRA
import sqlite3
import requests
import constants
import os, subprocess, sys, json

class JIRAConnect():

	proxy_dict = {"http": "http://proxy.lbs.alcatel-lucent.com:8000", "https": "http://proxy.lbs.alcatel-lucent.com:8000"}
	header_dict = {"User-Agent": "EnableIssues", "content-type": "application/json","Authorization": constants.TOKEN}
	base_directory = '/home/meet/'

	def __init__(self):
		self.jira = None
		self.connect()

	def connect(self):
		server = {'server': 'http://mvjira.mv.usa.alcatel.com:8080/'}
		self.jira = JIRA(server, basic_auth=('bot', 'tigris1!'))
		print 'connected to jira api!'

	def runcmd(self, cmd_to_run, cwd=None, shell=False):
		proc = subprocess.Popen(cmd_to_run, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True)
		out, err = proc.communicate()
		ec = proc.returncode
		del proc
		return [ec, out, err]

	def preprocess_data_before_write(self,error_dict):
		no_commit_branch_dict = {}
		partial_commit_branch_dict = {}
		all_branch_commit_dict = {}

		for key, value in error_dict.items():
			value = str(value)
			if ('True' not in value or 'False' not in value):
				if 'True' not in value:
					no_commit_branch_dict[key] = value
				else:
					all_branch_commit_dict[key] = value
			else:
				partial_commit_branch_dict[key] = value

		return (no_commit_branch_dict, partial_commit_branch_dict, all_branch_commit_dict)

	def write_to_sqlite_db(self,error_dict, flag):
		table_name = ''
		if flag == 1:
			table_name = 'branch_with_all_commits'
		elif flag == 0:
			table_name = 'branch_with_no_commits'
		else:
			table_name = 'branch_with_partial_commits'

		if error_dict != {}:
			try:
				conn = sqlite3.connect('jira_reports.db')
				if conn == None:
					print "error writing to sqlite db!"
					return
				c = conn.cursor()
				for key, value in error_dict.items():
					c.execute('INSERT INTO '+table_name+' VALUES (?,?)', [key,str(value)])
			except sqlite3.Error as e:
				print("An error occurred while writing to sqlite db ", e.args[0])

			if conn != None:
				conn.commit()
				conn.close()



	def get_all_projects(self):
		return self.jira.projects()

	def get_all_issues_for_project(self, project, block_num, block_size):
		print "getting issues for project " + project + " from id " + str(block_num) + " upto " + str(block_size) + " issues!"
		return self.jira.search_issues('project='+project, startAt=block_num, maxResults=block_size)

	def get_issues_by_created_date(self, project, created_date, block_num, block_size):
		print "getting issues for project " + project + " from id " + str(block_num) + " upto " + str(block_size) + " issues!"
		return self.jira.search_issues('project='+project+' and createdDate >= '+created_date+' and type=Bug', startAt=block_num, maxResults=block_size)
		

	def get_labels_affects_releases(self, issue):
		issue_dict = {}
		labels_arr = []
		issue = self.jira.issue(issue)
		# for labels in issue.fields.labels:
		# 	labels_arr.append(labels)
		for affect_releases in issue.fields.customfield_11101:
			labels_arr.append(affect_releases.value)
		if not '0.0' in labels_arr:
			labels_arr.append('0.0')
		# for field_name in issue.raw['fields']:
		# 	print "Field:", field_name, "Value:", issue.raw['fields'][field_name]

		issue_dict['labels'] = labels_arr
		issue_dict['since'] = issue.fields.created
		issue_dict['name'] = str(issue)
		return issue_dict

	def get_git_commits_for_branch_api(self, branch, since, name):
		i = 0
		while True:
			commit_api_url = constants.URL_ROOT + '/repos/' + constants.USER_ID + '/VCA/commits?sha=vca-'+branch+'&page='+str(i)+'&since='+since
			i += 1
			commits  = requests.get(commit_api_url, headers = self.header_dict, proxies = self.proxy_dict, verify = False)
			commit_data = json.loads(commits.text)
			for commit in commit_data:
				if 'commit' in commit > 0:
					if name in commit['commit']['message'].encode('utf-8'):
						return True
			if 'next' not in commits.links:
				break;
		return False

	def check_and_import_repo(self, repository):
		path = self.base_directory;
		print "checking repository: ",repository," at path: ",path
		if os.path.isdir(path+repository):
			rc, stdout, errout = self.runcmd(['git', 'fetch'], cwd=path+repository)
			if rc != 0:
				print "warning: Failed to update repo", repository, errout
				sys.exit(1)
		else:
			rc, stdout, errout = self.runcmd(['git', 'clone', "git@github.mv.usa.alcatel.com:VCA/VCA.git", path+repository])
			if rc != 0:
				print "error: Failed to clone repository", repository, errout
				sys.exit(1)



	def get_git_commits_for_branch_log(self, branch, since, name, repository):
		branch_name = 'origin/vca-'+branch
		# rc, stdout, errout = self.runcmd(["git", "checkout",branch_name,"-f"], cwd=self.base_directory+repository)
		# if rc != 0:
		# 	print "error: Failed to checkout branch ",branch_name, repository,errout
		# 	sys.exit(1)
		#rc, stdout, errout = self.runcmd(["git", "log", "--first-parent", branch_name, "--oneline", "--after", since], cwd=self.base_directory+repository)
		if branch_name == 'vca-master':
			rc, stdout, errout = self.runcmd(["git", "log", "--first-parent", branch_name, "--oneline", "--pretty=format:'%h%x09%an%x09%ad%x09%s'","--grep", name], cwd=self.base_directory+repository)
		else:
			rc, stdout, errout = self.runcmd(["git", "log", "--no-merges", branch_name, "--oneline", "--pretty=format:'%h%x09%an%x09%ad%x09%s'","--grep", name], cwd=self.base_directory+repository)
		if rc != 0:
			print "error: Failed to get log messages from repo", repository,errout
			sys.exit(1)
		if len(stdout.rstrip()) > 0:
			return 'True '+stdout.rstrip()
		return False

		

if __name__ == '__main__':
    jira_client = JIRAConnect()
    block_size = 100
    block_num = 0

    jira_client.check_and_import_repo('VCA')

    while True:
    	error_dict = {}
    	start_idx = block_num*block_size
    	print start_idx
    	all_issues = jira_client.get_issues_by_created_date('VRS','2018-01-01', start_idx, block_size)
    	if len(all_issues) == 0:
    		# Retrieve issues until there are no more to come
    		break
    	block_num += 1


    	for issue in all_issues:
    		issue = str(issue)
    		issue_dict = jira_client.get_labels_affects_releases(issue)
    		if issue_dict == None:
    			continue
    		error_dict[issue] = {}

    		for branch in issue_dict['labels']:
    			if branch == '0.0':
    				branch = 'master'
    			result = jira_client.get_git_commits_for_branch_log(branch, str(issue_dict['since']), issue, 'VCA')
    			error_dict[issue]['VCA-'+branch] = result

    	(no_commit_branch_dict, partial_commit_branch_dict, all_branch_commit_dict) = jira_client.preprocess_data_before_write(error_dict)
    	jira_client.write_to_sqlite_db(all_branch_commit_dict, 1)
    	jira_client.write_to_sqlite_db(no_commit_branch_dict, 0)
    	jira_client.write_to_sqlite_db(partial_commit_branch_dict, -1)

    # error_dict = {}
    # start_idx = block_num*block_size
    # print start_idx
    # all_issues = jira_client.get_issues_by_created_date('VRS', '2018-01-01')
    # if len(all_issues) == 0:
    # 	# Retrieve issues until there are no more to come
    # 	exit(1)
    # for issue in all_issues:
    # 	issue = str(issue)
    # 	issue_dict = jira_client.get_labels_affects_releases(issue)
    # 	error_dict[issue] = {}
    # 	for branch in issue_dict['labels']:
    # 		if branch == '0.0':
    # 			branch = 'master'
    # 		result = jira_client.get_git_commits_for_branch_log(branch, str(issue_dict['since']), issue, 'VCA')
    # 		error_dict[issue]['VCA-'+branch] = result

    # print "error_dict",error_dict
    # jira_client.write_to_file(error_dict)