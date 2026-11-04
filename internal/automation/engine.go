package automation

import (
	"context"
	"fmt"
	"github.com/levyvix/league-auto-accept/internal/config"
	"github.com/levyvix/league-auto-accept/internal/lcu"
	"strconv"
	"strings"
	"time"
)

type Action struct {
	ID        int    `json:"id"`
	Actor     int    `json:"actorCellId"`
	Champion  int    `json:"championId"`
	Type      string `json:"type"`
	Completed bool   `json:"completed"`
	Active    bool   `json:"isInProgress"`
}
type Player struct {
	Cell     int    `json:"cellId"`
	Position string `json:"assignedPosition"`
}
type Swap struct {
	ID        int    `json:"id"`
	State     string `json:"state"`
	Direction string `json:"direction"`
}
type Session struct {
	Bans struct {
		Mine   []int `json:"myTeamBans"`
		Theirs []int `json:"theirTeamBans"`
	} `json:"bans"`
	Local          int        `json:"localPlayerCellId"`
	Team           []Player   `json:"myTeam"`
	Actions        [][]Action `json:"actions"`
	Swaps          []Swap     `json:"swaps"`
	PickOrderSwaps []Swap     `json:"pickOrderSwaps"`
	Custom         bool       `json:"isCustomGame"`
	GameID         int64      `json:"gameId"`
	Chat           struct {
		ID string `json:"multiUserChatId"`
	} `json:"chatDetails"`
	Timer struct {
		Phase     string `json:"phase"`
		Total     int    `json:"totalTimeInPhase"`
		Remaining int    `json:"adjustedTimeLeftInPhase"`
	} `json:"timer"`
}
type Engine struct {
	API                           lcu.API
	Phase, Position, Mode, Notice string
	started                       time.Time
	room                          string
	selected                      map[int]int
	lastPhase                     string
	requeued, honor               bool
}

func New(api lcu.API) *Engine { return &Engine{API: api, selected: map[int]int{}} }
func Normalize(s string) string {
	s = strings.ToUpper(strings.TrimSpace(s))
	switch s {
	case "MID":
		return "MIDDLE"
	case "ADC", "BOT":
		return "BOTTOM"
	case "SUP", "SUPPORT":
		return "UTILITY"
	}
	return s
}
func Candidates(s config.Settings, position, mode string, custom bool) []int {
	position = Normalize(position)
	primary, secondary := Normalize(s.PrimaryPosition), Normalize(s.SecondaryPosition)
	first := false
	if position == "" {
		if mode == "CLASSIC" && !custom {
			return nil
		}
		first = true
	} else if primary == "FILL" || position == primary {
		first = true
	} else if position == secondary {
	} else {
		return nil
	}
	ids := []string{s.SecondaryID, s.SecondaryBackupID}
	if first {
		ids = []string{s.ChampID, s.BackupID}
	}
	var result []int
	for _, id := range ids {
		n, e := strconv.Atoi(id)
		if e == nil && n > 0 && (len(result) == 0 || result[0] != n) {
			result = append(result, n)
		}
	}
	return result
}
func (e *Engine) Preferences(ctx context.Context, s *config.Settings) error {
	var lobby struct {
		Local struct {
			First  string `json:"firstPositionPreference"`
			Second string `json:"secondPositionPreference"`
			Nested struct {
				First  string `json:"firstPreference"`
				Second string `json:"secondPreference"`
			} `json:"positionPreferences"`
		} `json:"localMember"`
	}
	if err := e.API.Request(ctx, "GET", "lol-lobby/v2/lobby", nil, &lobby); err != nil {
		return err
	}
	if lobby.Local.First == "" {
		lobby.Local.First = lobby.Local.Nested.First
		lobby.Local.Second = lobby.Local.Nested.Second
	}
	if lobby.Local.First != "" {
		s.PrimaryPosition = Normalize(lobby.Local.First)
		s.SecondaryPosition = Normalize(lobby.Local.Second)
	}
	return nil
}
func (e *Engine) Step(ctx context.Context, s *config.Settings) error {
	var flow struct {
		Phase string `json:"phase"`
		Data  struct {
			Queue struct {
				Mode string `json:"gameMode"`
			} `json:"queue"`
		} `json:"gameData"`
	}
	if err := e.API.Request(ctx, "GET", "lol-gameflow/v1/session", nil, &flow); err != nil {
		return err
	}
	e.Phase = flow.Phase
	e.Mode = flow.Data.Queue.Mode
	e.Notice = ""
	if e.Phase == "Lobby" || e.Phase == "Matchmaking" || e.Phase == "ReadyCheck" {
		_ = e.Preferences(ctx, s)
	}
	if e.Phase != "ChampSelect" {
		e.room = ""
		e.started = time.Time{}
		e.Position = ""
	}
	if e.Phase == "Matchmaking" {
		e.requeued = false
	}
	if e.Phase == "InProgress" {
		e.honor = false
	}
	switch e.Phase {
	case "ReadyCheck":
		if s.AutoAccept && e.lastPhase != "ReadyCheck" {
			if err := e.API.Request(ctx, "POST", "lol-matchmaking/v1/ready-check/accept", nil, nil); err != nil {
				return err
			}
		}
	case "ChampSelect":
		if s.AutoAccept || s.AutoSwap {
			if err := e.Select(ctx, *s); err != nil {
				return err
			}
		}
	case "PreEndOfGame":
		if s.AutoRequeue && !e.honor {
			if err := e.API.Request(ctx, "POST", "lol-honor-v2/v1/skip-honor-vote", nil, nil); err == nil {
				e.honor = true
			}
		}
	case "EndOfGame":
		if s.AutoRequeue && !e.requeued {
			if err := e.API.Request(ctx, "POST", "lol-lobby/v2/play-again", nil, nil); err != nil {
				return err
			}
		}
	case "Lobby":
		if e.lastPhase == "Matchmaking" || e.lastPhase == "ReadyCheck" {
			s.AutoRequeue = false
			e.Notice = "Queue cancelled: auto-requeue disabled"
		}
		if s.AutoRequeue && !e.requeued {
			if err := e.API.Request(ctx, "POST", "lol-lobby/v2/lobby/matchmaking/search", nil, nil); err != nil {
				return err
			}
			e.requeued = true
		}
	}
	e.lastPhase = e.Phase
	return nil
}
func (e *Engine) Select(ctx context.Context, s config.Settings) error {
	var session Session
	if err := e.API.Request(ctx, "GET", "lol-champ-select/v1/session", nil, &session); err != nil {
		return err
	}
	if e.started.IsZero() || session.Chat.ID != e.room {
		e.started = time.Now()
		e.room = session.Chat.ID
		e.selected = map[int]int{}
		e.Position = ""
	}
	for _, p := range session.Team {
		if p.Cell == session.Local && p.Position != "" {
			e.Position = Normalize(p.Position)
		}
	}
	if s.AutoSwap {
		swaps := append(session.Swaps, session.PickOrderSwaps...)
		for _, swap := range swaps {
			if swap.State == "RECEIVED" || swap.Direction == "INCOMING" || swap.Direction == "RECEIVED" {
				if err := e.API.Request(ctx, "POST", fmt.Sprintf("lol-champ-select/v1/session/swaps/%d/accept", swap.ID), nil, nil); err != nil {
					e.Notice = err.Error()
				}
			}
		}
	}
	if !s.AutoAccept {
		return nil
	}
	candidates := Candidates(s, e.Position, e.Mode, session.Custom)
	blocked := map[int]bool{}
	for _, id := range append(session.Bans.Mine, session.Bans.Theirs...) {
		blocked[id] = true
	}
	for _, group := range session.Actions {
		for _, a := range group {
			if a.Type == "pick" && a.Completed && a.Actor != session.Local {
				blocked[a.Champion] = true
			}
		}
	}
	available := candidates[:0]
	for _, id := range candidates {
		if !blocked[id] {
			available = append(available, id)
		}
	}
	candidates = available
	if len(candidates) == 0 {
		e.Notice = "No matching position: automatic pick paused"
	}
	for _, group := range session.Actions {
		for _, a := range group {
			if a.Actor != session.Local || a.Completed {
				continue
			}
			path := fmt.Sprintf("lol-champ-select/v1/session/actions/%d", a.ID)
			if a.Type == "pick" && s.AutoPick && len(candidates) > 0 {
				selected := e.selected[a.ID]
				valid := false
				for _, id := range candidates {
					if id == selected {
						valid = true
					}
				}
				if !valid {
					selected = 0
					delete(e.selected, a.ID)
				}
				if selected == 0 && (time.Since(e.started).Milliseconds() >= int64(s.HoverDelay) || session.Timer.Phase != "PLANNING") {
					for _, id := range candidates {
						if err := e.API.Request(ctx, "PATCH", path, map[string]any{"championId": id}, nil); err == nil {
							selected = id
							e.selected[a.ID] = id
							break
						}
					}
				}
				if a.Active && selected > 0 && (s.InstaLock || session.Timer.Remaining <= s.LockEnd || session.Timer.Total-session.Timer.Remaining >= s.LockDelay) {
					if err := e.API.Request(ctx, "PATCH", path, map[string]any{"championId": selected, "completed": true}, nil); err != nil {
						return err
					}
				}
			}
			if a.Type == "ban" && s.AutoBan && a.Active && session.Timer.Phase != "PLANNING" {
				id, _ := strconv.Atoi(s.BanID)
				if id <= 0 {
					continue
				}
				lock := s.InstaBan || session.Timer.Remaining <= s.BanLockEnd || session.Timer.Total-session.Timer.Remaining >= s.BanLockDelay
				if err := e.API.Request(ctx, "PATCH", path, map[string]any{"championId": id, "completed": lock}, nil); err != nil {
					return err
				}
			}
		}
	}
	return nil
}
