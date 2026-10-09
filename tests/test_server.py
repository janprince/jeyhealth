"""Exercise detection and API access boundaries against an isolated database."""
import http.client
import json
import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path
from http.server import ThreadingHTTPServer
import server


class JeyHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.original_db = server.DB_PATH
        server.DB_PATH = Path(cls.tmp.name) / "test.sqlite3"
        server.init_db(seed=False)
        with server.connect() as db:
            for name, role in [("Official","official"),("Volunteer","chv"),("Nurse","clinic"),("Resident","resident")]:
                db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)", (name,role+"@test.local",server.password_hash("test-password"),role))
            db.execute("INSERT INTO localities VALUES(1,'Ablekuma','Ga West',5.65,-0.31)")
            db.execute("INSERT INTO localities VALUES(2,'Oduman','Ga West',5.66,-0.36)")
        cls.http = ThreadingHTTPServer(("127.0.0.1",0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join()
        server.DB_PATH=cls.original_db;cls.tmp.cleanup()

    def setUp(self):
        with server.connect() as db:
            for table in ("cluster_reports","events","clusters","reports","sessions","login_attempts","advisories"):
                db.execute(f"DELETE FROM {table}")
            db.execute("UPDATE settings SET value='5' WHERE key='threshold'")
            db.execute("UPDATE settings SET value='3' WHERE key='window_days'")
        self.cookie=None;self.csrf=None

    def request(self,path,body=None,csrf=True,origin=None):
        client=http.client.HTTPConnection("127.0.0.1",self.http.server_port)
        headers={}
        if self.cookie:headers["Cookie"]=self.cookie
        if csrf and self.csrf:headers["X-CSRF-Token"]=self.csrf
        if origin:headers["Origin"]=origin
        if body is not None:headers["Content-Type"]="application/json"
        client.request("POST" if body is not None else "GET","/api/"+path,json.dumps(body) if body is not None else None,headers)
        response=client.getresponse();status=response.status
        cookie=response.getheader("Set-Cookie")
        payload=response.read();client.close()
        try:data=json.loads(payload)
        except ValueError:data=payload.decode()
        return status,data,cookie

    def login(self,role):
        status,_,cookie=self.request("login",{"email":role+"@test.local","password":"test-password"})
        self.assertEqual(status,200);self.cookie=cookie.split(";")[0]
        status,data,_=self.request("state");self.assertEqual(status,200);self.csrf=data["user"]["csrf"]

    def report(self,**kw):
        payload={"locality_id":1,"category":server.CATEGORIES[0],"case_count":1,"observed_on":server.today_date().isoformat(),"notes":"Test observation.","submission_key":server.secrets.token_hex(16)}
        payload.update(kw)
        return self.request("reports",payload)

    def add_record(self,count=1,ago=0,locality=1,category=None,author=2,status="submitted"):
        with server.connect() as db:
            cur=db.execute("""INSERT INTO reports(locality_id,category,case_count,observed_on,notes,submitted_by,status,submission_key,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?,?)""",(locality,category or server.CATEGORIES[0],count,(server.today_date()-timedelta(days=ago)).isoformat(),"Test",author,status,server.secrets.token_hex(16),server.now(),server.now()))
            return cur.lastrowid

    def clusters(self):
        with server.connect() as db:
            server.detect_clusters(db)
            return [dict(c) for c in db.execute("SELECT * FROM clusters")]

    def test_threshold_is_inclusive_and_does_not_duplicate_alert(self):
        self.add_record(2);self.add_record(3,ago=2)
        self.assertEqual(len(self.clusters()),1)
        self.assertEqual(self.clusters()[0]["rolling_count"],5)
        self.assertEqual(len(self.clusters()),1)

    def test_window_excludes_fourth_calendar_day(self):
        self.add_record(4);self.add_record(3,ago=3)
        self.assertEqual(self.clusters(),[])

    def test_localities_and_symptom_categories_do_not_mix(self):
        self.add_record(3);self.add_record(3,locality=2);self.add_record(3,category=server.CATEGORIES[1])
        self.assertEqual(self.clusters(),[])

    def test_unverified_tips_and_dismissed_reports_do_not_count(self):
        self.add_record(4);self.add_record(5,author=4,status="unverified");self.add_record(5,status="dismissed")
        self.assertEqual(self.clusters(),[])

    def test_verified_resident_tip_counts(self):
        self.add_record(4);self.add_record(1,author=4,status="verified")
        self.assertEqual(self.clusters()[0]["rolling_count"],5)

    def test_ageing_evidence_preserves_cluster_history(self):
        r=self.add_record(5);self.clusters()
        with server.connect() as db:db.execute("UPDATE reports SET observed_on=? WHERE id=?",((server.today_date()-timedelta(days=10)).isoformat(),r))
        self.assertEqual(self.clusters()[0]["rolling_count"],0)
        with server.connect() as db:self.assertEqual(db.execute("SELECT count(*) FROM cluster_reports").fetchone()[0],1)

    def test_closed_cluster_does_not_reopen_without_new_evidence(self):
        self.add_record(5);cluster=self.clusters()[0]
        with server.connect() as db:db.execute("UPDATE clusters SET status='dismissed',updated_at=? WHERE id=?",(server.now(),cluster["id"]))
        self.assertEqual(len(self.clusters()),1)
        self.add_record(1)
        self.assertEqual(len(self.clusters()),2)

    def test_authentication_and_wrong_password(self):
        self.assertEqual(self.request("state")[0],401)
        self.assertEqual(self.request("login",{"email":"official@test.local","password":"wrong"})[0],401)

    def test_map_requests_can_send_origin_referrer(self):
        client=http.client.HTTPConnection("127.0.0.1",self.http.server_port)
        client.request("GET","/")
        response=client.getresponse()
        self.assertEqual(response.status,200)
        self.assertEqual(response.getheader("Referrer-Policy"),"strict-origin-when-cross-origin")
        self.assertIn("https://tile.openstreetmap.org",response.getheader("Content-Security-Policy"))
        response.read();client.close()

    def test_resident_only_sees_own_reports_and_no_clusters(self):
        self.add_record(5);self.add_record(1,author=4,status="unverified");self.clusters();self.login("resident")
        _,data,_=self.request("state")
        self.assertEqual(len(data["reports"]),1);self.assertEqual(data["clusters"],[])
        self.assertTrue(all(r["submitted_by"]==4 for r in data["reports"]))

    def test_worker_cannot_change_rules_or_publish_notices(self):
        self.login("chv")
        self.assertEqual(self.request("settings",{"threshold":2,"window_days":3,"notes":"test"})[0],403)
        self.assertEqual(self.request("advisories",{"title":"test","body":"test"})[0],403)

    def test_submission_idempotency(self):
        self.login("chv");key=server.secrets.token_hex(16)
        first=self.report(submission_key=key);second=self.report(submission_key=key)
        self.assertEqual(first[0],201);self.assertEqual(second[0],200)
        self.assertEqual(first[1]["id"],second[1]["id"])
        with server.connect() as db:self.assertEqual(db.execute("SELECT count(*) FROM reports").fetchone()[0],1)

    def test_input_validation_and_csrf(self):
        self.login("chv")
        self.assertEqual(self.report(case_count=-1)[0],400)
        self.assertEqual(self.report(case_count=1.5)[0],400)
        self.assertEqual(self.report(category="Unknown")[0],400)
        self.assertEqual(self.report(observed_on=(server.today_date()+timedelta(days=1)).isoformat())[0],400)
        self.assertEqual(self.report(locality_id=999)[0],400)
        self.assertEqual(self.request("reports",{},csrf=False)[0],403)
        self.assertEqual(self.request("logout",{},origin="https://untrusted.example")[0],403)

    def test_tip_verification_triggers_alert_with_history(self):
        self.add_record(4);r=self.add_record(1,author=4,status="unverified")
        self.login("official")
        self.assertEqual(self.request("reports/review",{"id":r,"status":"verified","notes":"Checked with volunteer."})[0],200)
        self.assertEqual(len(self.clusters()),1)
        _,data,_=self.request("state")
        self.assertTrue(any(e["action"]=="Report verified" for e in data["events"]))

    def test_cluster_review_requires_notes_and_enforces_transitions(self):
        self.add_record(5);c=self.clusters()[0];self.login("official")
        self.assertEqual(self.request("clusters/review",{"id":c["id"],"status":"escalated","notes":""})[0],400)
        self.assertEqual(self.request("clusters/review",{"id":c["id"],"status":"escalated","notes":"Evidence reviewed."})[0],200)
        self.assertEqual(self.request("clusters/review",{"id":c["id"],"status":"dismissed","notes":"Invalid transition."})[0],409)
        self.assertEqual(self.request("clusters/review",{"id":c["id"],"status":"resolved","notes":"Response completed."})[0],200)

    def test_advisory_visible_to_resident_and_logout_revokes_session(self):
        self.login("official")
        self.assertEqual(self.request("advisories",{"title":"Community notice","body":"Test message.","locality_id":1})[0],201)
        self.login("resident");_,data,_=self.request("state")
        self.assertEqual(data["advisories"][0]["title"],"Community notice")
        self.assertEqual(self.request("logout",{})[0],200)
        self.assertEqual(self.request("state")[0],401)

    def test_changing_rule_recalculates_and_export_is_official_only(self):
        self.add_record(3);self.login("official")
        self.assertEqual(self.request("settings",{"threshold":3,"window_days":3,"notes":"Test rule."})[0],200)
        self.assertEqual(len(self.clusters()),1)
        status,csv,_=self.request("export");self.assertEqual(status,200);self.assertIn("Report ID,Locality",csv)
        self.login("resident");self.assertEqual(self.request("export")[0],403)


if __name__=="__main__":unittest.main()
