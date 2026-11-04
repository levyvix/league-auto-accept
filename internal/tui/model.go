package tui

import (
	"charm.land/bubbles/v2/textinput"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"context"
	"fmt"
	"github.com/levyvix/league-auto-accept/internal/automation"
	"github.com/levyvix/league-auto-accept/internal/config"
	"github.com/levyvix/league-auto-accept/internal/lcu"
	"github.com/levyvix/league-auto-accept/internal/update"
	"log"
	"sort"
	"strconv"
	"strings"
	"time"
)

type Champion struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}
type tick struct{}
type releaseMsg struct {
	release update.Release
	err     error
}
type stagedMsg struct {
	path string
	err  error
}
type result struct {
	engine    *automation.Engine
	settings  config.Settings
	champions []Champion
	err       error
}
type Model struct {
	Settings                    config.Settings
	path                        string
	engine                      *automation.Engine
	champions                   []Champion
	input                       textinput.Model
	screen                      string
	cursor, slot, width, height int
	busy                        bool
	status                      string
	ctx                         context.Context
	release                     update.Release
}

func New(ctx context.Context, s config.Settings, path string) Model {
	input := textinput.New()
	input.Placeholder = "Search champion..."
	return Model{ctx: ctx, Settings: s, path: path, input: input, width: 80, height: 30, status: "Connecting to League Client..."}
}
func after() tea.Cmd { return tea.Tick(time.Second, func(time.Time) tea.Msg { return tick{} }) }
func (m Model) Init() tea.Cmd {
	return tea.Batch(after(), func() tea.Msg { r, e := update.Check(m.ctx); return releaseMsg{r, e} })
}
func (m Model) poll() tea.Cmd {
	s, e, champs, ctx := m.Settings, m.engine, m.champions, m.ctx
	return func() tea.Msg {
		if e == nil {
			client, err := lcu.Discover(ctx)
			if err != nil {
				return result{settings: s, err: err}
			}
			e = automation.New(client)
		}
		if err := e.Step(ctx, &s); err != nil {
			return result{settings: s, err: err}
		}
		if len(champs) == 0 {
			var summoner struct {
				ID int64 `json:"summonerId"`
			}
			if e.API.Request(ctx, "GET", "lol-summoner/v1/current-summoner", nil, &summoner) == nil {
				_ = e.API.Request(ctx, "GET", fmt.Sprintf("lol-champions/v1/inventories/%d/champions-minimal", summoner.ID), nil, &champs)
				champs = uniqueChampions(champs)
			}
		}
		return result{engine: e, settings: s, champions: champs}
	}
}

// uniqueChampions collapses repeated inventory entries and alternate IDs for
// the same display name, preferring the lowest (base champion) ID.
func uniqueChampions(champions []Champion) []Champion {
	ordered := append([]Champion(nil), champions...)
	sort.SliceStable(ordered, func(i, j int) bool { return ordered[i].ID < ordered[j].ID })
	ids, names := map[int]bool{}, map[string]bool{}
	result := make([]Champion, 0, len(ordered))
	for _, champion := range ordered {
		champion.Name = strings.TrimSpace(champion.Name)
		name := strings.ToLower(champion.Name)
		if champion.ID <= 0 || name == "" || name == "none" || ids[champion.ID] || names[name] {
			continue
		}
		ids[champion.ID], names[name] = true, true
		result = append(result, champion)
	}
	sort.SliceStable(result, func(i, j int) bool { return strings.ToLower(result[i].Name) < strings.ToLower(result[j].Name) })
	return result
}
func (m *Model) save() {
	if m.Settings.AutoSave {
		if err := config.Save(m.path, m.Settings); err != nil {
			m.status = err.Error()
		}
	}
}
func (m Model) filtered() []Champion {
	r := []Champion{{ID: 0, Name: "None"}}
	for _, c := range m.champions {
		if strings.Contains(strings.ToLower(c.Name), strings.ToLower(m.input.Value())) {
			r = append(r, c)
		}
	}
	return r
}
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch v := msg.(type) {
	case releaseMsg:
		if v.err == nil {
			m.release = v.release
			m.status = "Latest release: " + v.release.Tag + " · U to check / download native update"
		}
		return m, nil
	case stagedMsg:
		if v.err != nil {
			m.status = v.err.Error()
			return m, nil
		}
		if err := update.Launch(v.path); err != nil {
			m.status = err.Error()
			return m, nil
		}
		return m, tea.Quit
	case tea.WindowSizeMsg:
		m.width = v.Width
		m.height = v.Height
	case tick:
		if !m.busy {
			m.busy = true
			return m, m.poll()
		}
		return m, after()
	case result:
		m.busy = false
		m.engine = v.engine
		m.champions = v.champions
		if v.err != nil {
			m.status = v.err.Error()
			log.Print(v.err)
		} else {
			m.status = v.engine.Notice
			if v.engine.Notice == "Queue cancelled: auto-requeue disabled" {
				m.Settings.AutoRequeue = false
				m.save()
			}
			if m.Settings.PrimaryPosition != v.settings.PrimaryPosition || m.Settings.SecondaryPosition != v.settings.SecondaryPosition {
				m.Settings.PrimaryPosition = v.settings.PrimaryPosition
				m.Settings.SecondaryPosition = v.settings.SecondaryPosition
				m.save()
			}
		}
		return m, after()
	case tea.KeyPressMsg:
		key := v.String()
		if key == "ctrl+c" {
			return m, tea.Quit
		}
		if m.screen == "picker" {
			switch key {
			case "esc":
				m.screen = ""
				return m, nil
			case "up":
				m.cursor = max(0, m.cursor-1)
				return m, nil
			case "down":
				m.cursor = min(len(m.filtered())-1, m.cursor+1)
				return m, nil
			case "enter":
				cs := m.filtered()
				c := cs[min(m.cursor, len(cs)-1)]
				id := strconv.Itoa(c.ID)
				if c.ID > 0 {
					recent := &m.Settings.RecentChampions
					if m.slot == 4 {
						recent = &m.Settings.RecentBans
					}
					items := []string{id}
					for _, old := range *recent {
						if old != id && len(items) < 5 {
							items = append(items, old)
						}
					}
					*recent = items
				}
				switch m.slot {
				case 0:
					m.Settings.ChampID = id
					m.Settings.ChampName = c.Name
				case 1:
					m.Settings.BackupID = id
					m.Settings.BackupName = c.Name
				case 2:
					m.Settings.SecondaryID = id
					m.Settings.SecondaryName = c.Name
				case 3:
					m.Settings.SecondaryBackupID = id
					m.Settings.SecondaryBackupName = c.Name
				case 4:
					m.Settings.BanID = id
					m.Settings.BanName = c.Name
				}
				m.save()
				if m.slot < 3 {
					m.slot++
					m.cursor = 0
					m.input.Reset()
				} else {
					m.screen = ""
				}
				return m, nil
			}
			var cmd tea.Cmd
			m.input, cmd = m.input.Update(msg)
			m.cursor = 0
			return m, cmd
		}
		if key == "q" || key == "esc" {
			if m.screen != "" {
				m.screen = ""
				return m, nil
			}
			return m, tea.Quit
		}
		if m.screen == "settings" {
			switch key {
			case "p":
				m.Settings.AutoPick = !m.Settings.AutoPick
			case "a":
				m.Settings.AutoBan = !m.Settings.AutoBan
			case "l":
				m.Settings.InstaLock = !m.Settings.InstaLock
			case "b":
				m.Settings.InstaBan = !m.Settings.InstaBan
			case "r":
				m.Settings.AutoRequeue = !m.Settings.AutoRequeue
			case "w":
				m.Settings.AutoSwap = !m.Settings.AutoSwap
			case "s":
				m.Settings.AutoSave = !m.Settings.AutoSave
				if err := config.Save(m.path, m.Settings); err != nil {
					m.status = err.Error()
				}
			}
			m.save()
			return m, nil
		}
		switch key {
		case "u":
			if m.release.Tag == "" {
				return m, func() tea.Msg { r, e := update.Check(m.ctx); return releaseMsg{r, e} }
			}
			m.screen = "update"
		case "y":
			if m.screen == "update" {
				r, ctx := m.release, m.ctx
				m.status = "Downloading native update..."
				return m, func() tea.Msg { p, e := update.Stage(ctx, r); return stagedMsg{p, e} }
			}
		case "1":
			m.Settings.AutoAccept = !m.Settings.AutoAccept
			m.save()
		case "2", "3":
			m.screen = "picker"
			m.slot = 0
			if key == "3" {
				m.slot = 4
			}
			m.cursor = 0
			m.input.Reset()
			return m, m.input.Focus()
		case "4":
			m.screen = "settings"
		}
	}
	return m, nil
}
func on(b bool) string {
	if b {
		return "ON"
	}
	return "OFF"
}
func (m Model) View() tea.View {
	title := lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#C9AA71"))
	muted := lipgloss.NewStyle().Foreground(lipgloss.Color("#8B9CAF"))
	accent := lipgloss.NewStyle().Foreground(lipgloss.Color("#51D9C0"))
	phase, position := "Offline", "—"
	if m.engine != nil && !m.busy {
		phase = m.engine.Phase
		position = m.engine.Position
	}
	lines := []string{title.Render("LEAGUE AUTO ACCEPT  /  GO"), muted.Render("Native LCU automation · foreground session"), "", accent.Render("Phase: " + phase + "   Position: " + position), ""}
	switch m.screen {
	case "update":
		lines = append(lines, title.Render("Native update"), "Latest: "+m.release.Tag, m.release.URL, "Y  Download and restart · Esc  Cancel")
	case "settings":
		lines = append(lines, title.Render("Automation settings"), fmt.Sprintf("P  Auto-pick       %s", on(m.Settings.AutoPick)), fmt.Sprintf("A  Auto-ban        %s", on(m.Settings.AutoBan)), fmt.Sprintf("L  Instant lock    %s", on(m.Settings.InstaLock)), fmt.Sprintf("B  Instant ban     %s", on(m.Settings.InstaBan)), fmt.Sprintf("R  Auto-requeue    %s", on(m.Settings.AutoRequeue)), fmt.Sprintf("W  Accept swaps    %s", on(m.Settings.AutoSwap)), fmt.Sprintf("S  Save settings   %s", on(m.Settings.AutoSave)), "", "Esc / Q  Back")
	case "picker":
		names := []string{"Primary champion", "Primary backup", "Secondary champion", "Secondary backup", "Ban champion"}
		lines = append(lines, title.Render(names[m.slot]), m.input.View(), "")
		cs := m.filtered()
		count := max(3, m.height-14)
		start := max(0, m.cursor-count+1)
		for i := start; i < len(cs) && i < start+count; i++ {
			name := "  " + cs[i].Name
			if i == m.cursor {
				name = accent.Render("› " + cs[i].Name)
			}
			lines = append(lines, name)
		}
		lines = append(lines, "", "↑/↓ Navigate · Enter Select · Esc Back")
	default:
		lines = append(lines, fmt.Sprintf("Auto-accept %s   Pick %s   Ban %s", on(m.Settings.AutoAccept), on(m.Settings.AutoPick), on(m.Settings.AutoBan)), "", fmt.Sprintf("Primary   %-10s  %s / %s", m.Settings.PrimaryPosition, m.Settings.ChampName, m.Settings.BackupName), fmt.Sprintf("Secondary %-10s  %s / %s", m.Settings.SecondaryPosition, m.Settings.SecondaryName, m.Settings.SecondaryBackupName), "Ban: "+m.Settings.BanName, "", muted.Render("Autofill: champion selection paused"), "", "1  Toggle automation   2  Champions   3  Ban", "4  Settings            Q  Quit")
	}
	if m.status != "" {
		lines = append(lines, "", muted.Render(m.status))
	}
	view := tea.NewView(lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#324A64")).Padding(1, 2).Width(max(20, min(96, m.width-2))).Render(strings.Join(lines, "\n")))
	view.AltScreen = true
	view.WindowTitle = "League Auto Accept"
	return view
}
