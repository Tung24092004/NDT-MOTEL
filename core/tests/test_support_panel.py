"""Support navigation must resolve safely for every role."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import resolve, reverse


class PanelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))


class SupportPanelTests(TestCase):
    def test_role_navigation_and_public_targets(self):
        users = [None, User.objects.create_user("support-user"),
                 User.objects.create_user("support-admin", is_staff=True),
                 User.objects.create_user("support-super", is_superuser=True)]
        help_path = reverse("trung_tam_tro_giup")
        help_parser = PanelParser()
        help_parser.feed(self.client.get(help_path).content.decode())
        anchors = {"help-room", "help-booking", "help-contract", "help-invoice", "help-repair", "help-smart"}
        self.assertTrue(anchors <= help_parser.ids)
        for user in users:
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                response = self.client.get(reverse("home"))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertEqual(html.count('id="ndtSupport"'), 1)
                self.assertEqual(html.count('src="/static/js/support-panel.js"'), 1)
                panel = html.split('id="ndtSupport"', 1)[1].split('</section>', 1)[0]
                self.assertIn('aria-expanded="false"', panel)
                self.assertNotIn("chatbot", panel.lower())
                parser = PanelParser()
                parser.feed(panel)
                self.assertEqual(len(parser.links), 10)
                fragments = set()
                for link in parser.links:
                    target = urlsplit(link)
                    resolve(target.path)
                    if target.fragment:
                        target_parser = PanelParser()
                        target_parser.feed(self.client.get(target.path).content.decode())
                        self.assertIn(target.fragment, target_parser.ids)
                        if target.path == help_path:
                            fragments.add(target.fragment)
                    self.assertIn(target.path, [help_path, reverse("home"), reverse("huong_dan_thue_phong")])
                self.assertEqual(fragments, anchors)
                first = "help-contract" if user and not user.is_staff and not user.is_superuser else "help-room"
                self.assertEqual(urlsplit(parser.links[1]).fragment, first)
