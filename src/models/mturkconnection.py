import os
import sys
import boto3
import xmltodict
import json
import datetime

#QuestionContent,Question,QuestionForm,Overview,AnswerSpecification,SelectionAnswer,FormattedContent,FreeTextAnswer

class MTurkConnection(object):
    def __init__(self, 
                 access_key=None, 
                 secret_key=None, 
                 email=None, 
                 hitpayment=0.01, 
                 running=False, 
                 hitid=None, 
                 title="News Classification Task", 
                 description="Classify a set of news articles as part of an academic research study.",
                 keywords="news, classification, research, academic",
                 environment="development",
                 bonus=0.0,
                 **kwargs):
        self.title = title
        self.description = description
        self.keywords = keywords
        self.access_key = access_key
        self.secret_key = secret_key
        self.email = email
        self.running = running
        self.hitpayment = hitpayment
        self.host = 'mechanicalturk.amazonaws.com' if environment == 'production' else 'mechanicalturk.sandbox.amazonaws.com'
        self.admin_host = 'https://requester.mturk.com' if environment == 'production' else 'https://requestersandbox.mturk.com'
        self.bonus = float(bonus)
        environments = {
            "production": {
                "endpoint": "https://mturk-requester.us-east-1.amazonaws.com",
                "preview": "https://www.mturk.com/mturk/preview",
                "manage": "https://requester.mturk.com/mturk/manageHITs"
            },
            "sandbox": {
                "endpoint": "https://mturk-requester-sandbox.us-east-1.amazonaws.com",
                "preview": "https://workersandbox.mturk.com/mturk/preview",
                "manage": "https://requestersandbox.mturk.com/mturk/manageHITs"
            },
        }
        self.mturk_environment = environments["production"] if environment == 'production' else environments["sandbox"]
        self.client = boto3.client('mturk',
            endpoint_url = self.mturk_environment['endpoint'], 
            region_name = 'us-east-1', 
            aws_access_key_id = self.access_key, 
            aws_secret_access_key = self.secret_key)
        self.hit_id = hitid

    def try_auth(self, access_key = None, secret_key = None):
        return True if self.get_balance() else False

    def get_balance(self):
        try:
            balance = self.client.get_account_balance()['AvailableBalance']
            print("Account balance: %s" % (balance))
            #print("Account balance: %d" % (balance['AvailableBalance']))
            return balance
        except:
            print("Problem getting account balance")
            return None

    def get_all_hits(self):
        return [hit['HITId'] for hit in self.client.list_hits()['HITs']]
    
    def serialize(self):
        return { 'access_key' : self.access_key,
                 'secret_key' : self.secret_key,
                 'email' : self.email,
                 'running' : self.running,
                 'admin_host': self.admin_host,
                 'hitpayment' : self.hitpayment,
                 'hitid' : self.hit_id,
                 'title' : self.title,
                 'description' : self.description,
                 'keywords' : self.keywords,
                 'bonus' : self.bonus}
    @classmethod
    def deserialize(cls, d):
        return MTurkConnection(**d)

    def begin_run(self, max_assignments=1, url="https://www.google.com"):
        question_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ExternalQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2006-07-14/ExternalQuestion.xsd">
          <ExternalURL>QUESTION_URL</ExternalURL>
          <FrameHeight>0</FrameHeight>
        </ExternalQuestion>
        """

        question_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <QuestionForm xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/QuestionForm.xsd">
        <Overview>
            <Title>{title}</Title>
            <FormattedContent><![CDATA[
                <p>{description}</p>
                <p>To begin, navigate to the following url: <a href="{url1}">{url2}</a></p>
            ]]></FormattedContent>
        </Overview>
        <Question>
            <QuestionIdentifier>secretcode</QuestionIdentifier>
            <DisplayName>Secret Code</DisplayName>
            <IsRequired>true</IsRequired>
            <QuestionContent>
                <Text>
                    Enter the 16 character secret code that you will receive after you complete this task.
                </Text>
            </QuestionContent>
            <AnswerSpecification>
                <FreeTextAnswer>
                    <Constraints>
                        <Length minLength="16" maxLength="16"/>
                    </Constraints>
                </FreeTextAnswer>
            </AnswerSpecification>
        </Question>
        </QuestionForm>
        """.format(title = self.title, description = self.description, url1 = url, url2 = url)

        hitinfo = self.client.create_hit(
            MaxAssignments=max_assignments,
            Title=self.title,
            Description=self.description,
            LifetimeInSeconds=14400,
            AssignmentDurationInSeconds=60 * 60 * 2,
            Keywords=self.keywords,
            Reward=str(self.hitpayment),
            QualificationRequirements=[{
                    'QualificationTypeId': '00000000000000000071',
                    'Comparator': 'EqualTo',
                    'LocaleValues': [{
                            'Country': 'US',
                    }]
            }],
            Question = question_xml.replace("QUESTION_URL", url)
            # Question='<p>'+self.description+' To begin, navigate to the following url: <a href="'+url+'">%('+url+')s</a>.</p>'
        )

        self.hit_type_id = hitinfo['HIT']['HITTypeId']
        self.hit_id = hitinfo['HIT']['HITId']
        print("\nCreated HIT: %s" % self.hit_id)
        print("You can view the HIT here: ")
        print(self.mturk_environment['preview'] + "?groupId={}".format(self.hit_type_id))
        print("And manage the results here: ")
        print(self.mturk_environment['manage'])

        # qc1 = boto.mturk.question.QuestionContent()
        # qc1.append_field('Title','Secret Code')
        # qc1.append_field('Text', 'Enter the 16 character secret code that you will receive after you complete this task.')
        # fta1 = boto.mturk.question.FreeTextAnswer()
        # q1 = boto.mturk.question.Question(identifier='secretcode',
        #                                   content=qc1,
        #                                   answer_spec=boto.mturk.question.AnswerSpecification(fta1),
        #                                   is_required=True)

        self.running = True
        return True

    def end_run(self, bonus={}, already_paid=[]):
        if not self.hit_id and not self.running:
            return []
        paid_bonus = []
        try:
            worker_assignments = {}
            next_token=None
            while True:
                if next_token is None:
                    response = self.client.list_assignments_for_hit(HITId = self.hit_id, MaxResults = 100)
                else:
                    response = self.client.list_assignments_for_hit(HITId=self.hit_id, NextToken = next_token, MaxResults=100)

                for a in response['Assignments'] :
                    if a['WorkerId'] not in already_paid :
                        worker_assignments[a['WorkerId']] = a['AssignmentId']

                if 'NextToken' in response.keys():
                    next_token = response['NextToken']
                else:
                    break
                
            for workerid, assignmentid in worker_assignments.iteritems() :
                if workerid not in bonus :
                    print "Error in end_run: worker_id %s present on mturk but not in bonus dict." % workerid
                else :
                    bonus_amt = min(10, max(0.01, round(bonus[workerid] * self.bonus, 2)))
                    self.client.send_bonus(WorkerId=workerid,
                                           BonusAmount=str(bonus_amt),
                                           AssignmentId=assignmentid,
                                           Reason='Bonus for completion of task.')
                    paid_bonus.append({'workerid' : workerid,
                                       'percent' : bonus[workerid],
                                       'amount' : bonus_amt,
                                       'assignmentid' : assignmentid})
            self.client.update_expiration_for_hit(HITId = self.hit_id, ExpireAt = datetime.datetime(2019, 1, 1))
            print("Expired hit: ", self.hit_id)
        except:
            print "Error caught when trying to end run."
            raise
        self.running = False
        return paid_bonus

    def get_payments_to_make(self):
        if not self.hit_id and not self.running:
            return []
        else:
            all_assignments = []
            next_token = None 
            while True :
                try:
                    if next_token is None:
                        response = self.client.list_assignments_for_hit(HITId = self.hit_id, MaxResults = 100)
                    else:
                        response = self.client.list_assignments_for_hit(HITId=self.hit_id, NextToken = next_token, MaxResults=100)
        
                    all_assignments += [[a['AssignmentId'], a['WorkerId'], a['Answer'].partition("<FreeText>")[2].partition("</FreeText>")[0]] 
                                        for a in response['Assignments'] if a['AssignmentStatus'] == 'Submitted']
                    
                    if 'NextToken' in response.keys():
                        next_token = response['NextToken']
                    else:
                        return all_assignments
                except:
                    raise 

    def make_payments(self, assignment_ids=[]) :
        npayments = 0
        for assignmentid in assignment_ids:
            try:
                self.client.approve_assignment(AssignmentId=assignmentid)
                npayments += 1
            except:
                continue
        print("Successfully made %d of %d payments" % (npayments, len(assignment_ids)))

    def delete_hit(self):
        try:
            self.client.delete_hit(HITId=self.hit_id)
            print("Deleted hit: ", self.hit_id)
        except:
            try:
                self.client.update_expiration_for_hit(HITId = self.hit_id, ExpireAt = datetime.datetime(2019, 1, 1))
                self.client.delete_hit(HITId=self.hit_id)
                print("Expired and deleted hit: ", self.hit_id)
            except:
                print("Could not delete hit: ", self.hit_id)



if __name__=='__main__':
    ID = None
    action = None 
    if len(sys.argv) > 2:
        ID = sys.argv[2]
    if len(sys.argv) > 1:
        action = sys.argv[1]

    mturk = MTurkConnection(access_key="ACCESS", secret_key="SECRET", hitid = ID, bonus = 0.01)
    mturk.try_auth()

    if action == "-create":
        mturk.begin_run()
    elif action == "-details":
        response = mturk.client.get_hit(HITId = ID)
        for i in response['HIT']:
            if i == "Question":
                continue
            print(i, response['HIT'][i])
        response = mturk.client.list_assignments_for_hit(HITId = ID, MaxResults = 100)
        all_assignments = [[a['AssignmentStatus'], a['AssignmentId'], a['WorkerId'], a['Answer']] 
                                        for a in response['Assignments']]
        print(all_assignments)
    elif action == "-expire":
        mturk.client.update_expiration_for_hit(HITId = ID, ExpireAt = datetime.datetime(2019, 1, 1))
        print("Expired hit: ", ID)
    elif action == "-delete":
        mturk.end_run()
        mturk.delete_hit()
    elif action == "-pay":
        to_pay = mturk.get_payments_to_make()
        print("Payments to make: ", to_pay)
        mturk.make_payments([a[0] for a in to_pay])
    elif action == "-clear": # clears group
        hits = mturk.client.list_hits()['HITs']
        for hit in hits:
            groupid = hit['HITGroupId']
            hitid = hit['HITId']
            title = hit['Title']
            creation_date = hit['CreationTime']
            status = hit['HITStatus']
            print("GroupID: %s | HIT: %s | Created : %s | %s | %s" % (groupid, hitid, creation_date, title, status))

            if ID is not None and hit['HITGroupId'] != ID:
                continue
            elif status == "Reviewable":
                print("Deleting hit.", hitid)
                mturk.client.delete_hit(HITId = hitid)
            else:
                try:
                    mturk.client.update_expiration_for_hit(HITId = hitid, ExpireAt = datetime.datetime(2015, 1, 1))
                    mturk.client.delete_hit(HITId = hitid)
                    print("Expiring and deleting hit.", hitid)
                except:
                    print("Could not expire and delete hit ", hitid)
    else:
        hits = mturk.client.list_hits()['HITs']
        for hit in hits:
            groupid = hit['HITGroupId']
            hitid = hit['HITId']
            title = hit['Title']
            creation_date = hit['CreationTime']
            status = hit['HITStatus']
            print("GroupID: %s | HIT: %s | Created : %s | %s | %s" % (groupid, hitid, creation_date, title, status))
