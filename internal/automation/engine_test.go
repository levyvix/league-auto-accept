package automation

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/levyvix/league-auto-accept/internal/config"
	"testing"
)

type fakeAPI struct {
	calls    []string
	session  Session
	payloads []map[string]any
	reject   int
}

func (f *fakeAPI) Request(_ context.Context, m, p string, b, out any) error {
	f.calls = append(f.calls, m+" "+p)
	if b, ok := b.(map[string]any); ok {
		f.payloads = append(f.payloads, b)
		if b["championId"] == f.reject {
			return fmt.Errorf("champion unavailable")
		}
	}
	if out != nil {
		data, _ := json.Marshal(f.session)
		return json.Unmarshal(data, out)
	}
	return nil
}

func TestBackupIsHoveredAndLocked(t *testing.T) {
	s := config.Defaults()
	s.AutoAccept = true
	s.PrimaryPosition = "MIDDLE"
	s.ChampID = "10"
	s.BackupID = "11"
	s.InstaLock = true
	f := &fakeAPI{reject: 10, session: Session{Local: 1, Team: []Player{{Cell: 1, Position: "MIDDLE"}}, Actions: [][]Action{{{ID: 2, Actor: 1, Type: "pick", Active: true}}}}}
	f.session.Timer.Phase = "BAN_PICK"
	e := New(f)
	e.Mode = "CLASSIC"
	if err := e.Select(context.Background(), s); err != nil {
		t.Fatal(err)
	}
	if len(f.payloads) != 3 || f.payloads[2]["championId"] != 11 || f.payloads[2]["completed"] != true {
		t.Fatalf("backup not locked: %v", f.payloads)
	}
}

func TestBannedPrimaryUsesBackup(t *testing.T) {
	s := config.Defaults()
	s.AutoAccept = true
	s.PrimaryPosition = "MIDDLE"
	s.ChampID = "10"
	s.BackupID = "11"
	s.InstaLock = true
	f := &fakeAPI{session: Session{Local: 1, Team: []Player{{Cell: 1, Position: "MIDDLE"}}, Actions: [][]Action{{{ID: 2, Actor: 1, Type: "pick", Active: true}}}}}
	f.session.Bans.Mine = []int{10}
	f.session.Timer.Phase = "BAN_PICK"
	e := New(f)
	e.Mode = "CLASSIC"
	if err := e.Select(context.Background(), s); err != nil {
		t.Fatal(err)
	}
	if len(f.payloads) != 2 || f.payloads[0]["championId"] != 11 {
		t.Fatal(f.payloads)
	}
}
func TestPositionPools(t *testing.T) {
	s := config.Defaults()
	s.PrimaryPosition = "MIDDLE"
	s.SecondaryPosition = "BOTTOM"
	s.ChampID = "1"
	s.SecondaryID = "2"
	for _, tt := range []struct {
		position, mode string
		want           int
	}{{"MID", "CLASSIC", 1}, {"BOTTOM", "CLASSIC", 2}, {"UTILITY", "CLASSIC", 0}, {"", "CLASSIC", 0}, {"", "ARAM", 1}} {
		got := Candidates(s, tt.position, tt.mode, false)
		if tt.want == 0 && len(got) != 0 || tt.want != 0 && (len(got) != 1 || got[0] != tt.want) {
			t.Errorf("%+v: got %v", tt, got)
		}
	}
}
func TestDisabledActionsAndAutofill(t *testing.T) {
	for _, autofill := range []bool{false, true} {
		s := config.Defaults()
		s.AutoAccept = true
		s.PrimaryPosition = "MIDDLE"
		s.SecondaryPosition = "BOTTOM"
		s.ChampID = "1"
		s.BanID = "3"
		s.InstaLock = true
		s.InstaBan = true
		s.AutoBan = false
		s.AutoPick = autofill
		f := &fakeAPI{session: Session{Local: 1, Team: []Player{{Cell: 1, Position: "UTILITY"}}, Actions: [][]Action{{{ID: 1, Actor: 1, Type: "pick", Active: true, Champion: 99}, {ID: 2, Actor: 1, Type: "ban", Active: true}}}}}
		f.session.Timer.Phase = "BAN_PICK"
		e := New(f)
		e.Mode = "CLASSIC"
		if err := e.Select(context.Background(), s); err != nil {
			t.Fatal(err)
		}
		if len(f.calls) != 1 {
			t.Fatalf("unexpected mutations: %v", f.calls)
		}
	}
}
