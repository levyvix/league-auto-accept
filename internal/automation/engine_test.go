package automation

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/levyvix/league-auto-accept/internal/config"
	"strings"
	"testing"
	"time"
)

type fakeAPI struct {
	phase    string
	calls    []string
	session  Session
	payloads []map[string]any
	reject   int
	swaps    []Swap
	failPath string
}

type fakeClock struct {
	current time.Time
}

func (clock *fakeClock) Now() time.Time { return clock.current }

func (clock *fakeClock) Advance(duration time.Duration) {
	clock.current = clock.current.Add(duration)
}

func newTestEngine(api *fakeAPI) (*Engine, *fakeClock) {
	clock := &fakeClock{current: time.Unix(1, 0)}
	return newEngine(api, clock.Now), clock
}

func (f *fakeAPI) Request(_ context.Context, m, p string, b, out any) error {
	f.calls = append(f.calls, m+" "+p)
	if p == f.failPath {
		return fmt.Errorf("client not ready")
	}
	if p == "lol-gameflow/v1/session" && out != nil {
		data, _ := json.Marshal(map[string]string{"phase": f.phase})
		return json.Unmarshal(data, out)
	}
	if p == "lol-champ-select/v1/session/pick-order-swaps" && out != nil {
		data, _ := json.Marshal(f.swaps)
		return json.Unmarshal(data, out)
	}
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

func countRequest(calls []string, want string) int {
	count := 0
	for _, call := range calls {
		if call == want {
			count++
		}
	}
	return count
}

func TestHonorThenPlayAgainBeforeEndOfGame(t *testing.T) {
	f := &fakeAPI{phase: "PreEndOfGame"}
	e, clock := newTestEngine(f)
	s := config.Defaults()
	s.AutoRequeue = true
	if err := e.Step(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	if countRequest(f.calls, "POST lol-honor-v2/v1/skip-honor-vote") != 1 || countRequest(f.calls, "POST lol-lobby/v2/play-again") != 0 {
		t.Fatalf("honor should precede Play Again: %v", f.calls)
	}
	clock.Advance(2 * time.Second)
	if err := e.Step(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	if countRequest(f.calls, "POST lol-lobby/v2/play-again") != 1 {
		t.Fatalf("must play again while still PreEndOfGame: %v", f.calls)
	}
	f.phase = "Lobby"
	if err := e.Step(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	if countRequest(f.calls, "POST lol-lobby/v2/lobby/matchmaking/search") != 1 {
		t.Fatalf("must start search after reaching lobby: %v", f.calls)
	}
}

func TestHonorRetryInEndOfGame(t *testing.T) {
	f := &fakeAPI{phase: "EndOfGame", failPath: "lol-honor-v2/v1/skip-honor-vote"}
	e, clock := newTestEngine(f)
	s := config.Defaults()
	s.AutoRequeue = true
	_ = e.Step(context.Background(), &s)
	if e.Notice != "Could not skip honor; retrying" {
		t.Fatalf("failed skip must be visible and retried: notice=%q calls=%v", e.Notice, f.calls)
	}
	f.failPath = ""
	_ = e.Step(context.Background(), &s)
	if countRequest(f.calls, "POST lol-honor-v2/v1/skip-honor-vote") != 2 {
		t.Fatalf("skip must retry in EndOfGame: %v", f.calls)
	}
	clock.Advance(2 * time.Second)
	f.phase = "WaitingForStats"
	_ = e.Step(context.Background(), &s)
	f.phase = "PreEndOfGame"
	_ = e.Step(context.Background(), &s)
	if countRequest(f.calls, "POST lol-honor-v2/v1/skip-honor-vote") != 3 {
		t.Fatalf("post-game actions must reset for the next game: %v", f.calls)
	}
}

func TestDisabledRequeueDoesNotSkipHonor(t *testing.T) {
	f := &fakeAPI{phase: "PreEndOfGame"}
	_ = New(f).Step(context.Background(), new(config.Settings))
	if len(f.calls) != 1 {
		t.Fatal(f.calls)
	}
}

func TestRequeueRetriesIfClientStaysInLobby(t *testing.T) {
	const search = "lol-lobby/v2/lobby/matchmaking/search"
	f := &fakeAPI{phase: "Lobby"}
	e, clock := newTestEngine(f)
	s := config.Defaults()
	s.AutoRequeue = true
	step := func() {
		t.Helper()
		if err := e.Step(context.Background(), &s); err != nil {
			t.Fatal(err)
		}
	}
	count := func() int {
		n := 0
		for _, call := range f.calls {
			if call == "POST "+search {
				n++
			}
		}
		return n
	}
	step()
	step()
	if count() != 1 {
		t.Fatalf("expected cooldown, calls: %v", f.calls)
	}
	clock.Advance(5 * time.Second)
	step()
	if count() != 2 {
		t.Fatalf("expected retry after successful POST left client in Lobby: %v", f.calls)
	}
	f.phase = "Matchmaking"
	step()
	f.phase = "Lobby"
	step()
	if s.AutoRequeue || count() != 2 {
		t.Fatal("returning from matchmaking must not restart a cancelled search")
	}
}

func TestEnableAcceptDuringReadyCheck(t *testing.T) {
	f := &fakeAPI{phase: "ReadyCheck"}
	e := New(f)
	s := config.Defaults()
	if err := e.Step(context.Background(), &s); err != nil {
		t.Fatal(err)
	}
	s.AutoAccept = true
	for i := 0; i < 2; i++ {
		if err := e.Step(context.Background(), &s); err != nil {
			t.Fatal(err)
		}
	}
	count := 0
	for _, call := range f.calls {
		if call == "POST lol-matchmaking/v1/ready-check/accept" {
			count++
		}
	}
	if count != 1 {
		t.Fatalf("want one accept after enabling, got %d", count)
	}
}

func TestPickOrderSwapEndpointAndFallback(t *testing.T) {
	for _, embedded := range []bool{true, false} {
		swaps := []Swap{{ID: 7, State: "RECEIVED"}, {ID: 8, State: "SENT"}, {ID: 9, State: "DECLINED"}}
		f := &fakeAPI{}
		if embedded {
			f.session.PickOrderSwaps = swaps
		} else {
			f.swaps = swaps
		}
		s := config.Defaults()
		s.AutoSwap = true
		s.AutoAccept = false
		if err := New(f).Select(context.Background(), s); err != nil {
			t.Fatal(err)
		}
		posts := []string{}
		for _, call := range f.calls {
			if strings.HasPrefix(call, "POST ") {
				posts = append(posts, call)
			}
		}
		if len(posts) != 1 || posts[0] != "POST lol-champ-select/v1/session/pick-order-swaps/7/accept" {
			t.Fatalf("embedded=%v: %v", embedded, f.calls)
		}
	}
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
