package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLegacySettingsAndRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "settings.json")
	if err := os.WriteFile(path, []byte(`{"champ_id":"90","auto_accept_on":true,"primary_position":"MIDDLE"}`), 0600); err != nil {
		t.Fatal(err)
	}
	s, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if !s.AutoPick || !s.AutoBan || s.ChampID != "90" {
		t.Fatal(s)
	}
	s.AutoPick = false
	s.AutoBan = false
	if err = Save(path, s); err != nil {
		t.Fatal(err)
	}
	again, err := Load(path)
	if err != nil || again.AutoPick || again.AutoBan {
		t.Fatal(again, err)
	}
	if err = Save(path, again); err != nil {
		t.Fatal("replace existing settings", err)
	}
}
