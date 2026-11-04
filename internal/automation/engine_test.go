package automation

import (
	"context"
	"encoding/json"
	"github.com/levyvix/league-auto-accept/internal/config"
	"testing"
)

type fakeAPI struct {
	calls   []string
	session Session
}

func (f *fakeAPI) Request(_ context.Context, m, p string, b, out any) error {
	f.calls = append(f.calls, m+" "+p)
	if out != nil {
		data, _ := json.Marshal(f.session)
		return json.Unmarshal(data, out)
	}
	return nil
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
