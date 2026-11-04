package config

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Settings struct {
	ChampName           string   `json:"champ_name"`
	ChampID             string   `json:"champ_id"`
	BackupName          string   `json:"backup_champ_name"`
	BackupID            string   `json:"backup_champ_id"`
	SecondaryName       string   `json:"secondary_champ_name"`
	SecondaryID         string   `json:"secondary_champ_id"`
	SecondaryBackupName string   `json:"secondary_backup_champ_name"`
	SecondaryBackupID   string   `json:"secondary_backup_champ_id"`
	PrimaryPosition     string   `json:"primary_position"`
	SecondaryPosition   string   `json:"secondary_position"`
	BanName             string   `json:"ban_name"`
	BanID               string   `json:"ban_id"`
	Spell1Name          string   `json:"spell1_name"`
	Spell1ID            string   `json:"spell1_id"`
	Spell2Name          string   `json:"spell2_name"`
	Spell2ID            string   `json:"spell2_id"`
	AutoAccept          bool     `json:"auto_accept_on"`
	AutoPick            bool     `json:"auto_pick"`
	AutoBan             bool     `json:"auto_ban"`
	InstaLock           bool     `json:"insta_lock"`
	InstaBan            bool     `json:"insta_ban"`
	AutoRequeue         bool     `json:"auto_requeue"`
	AutoSwap            bool     `json:"auto_swap_accept"`
	AutoSave            bool     `json:"save_settings"`
	Preload             bool     `json:"preload_data"`
	HoverDelay          int      `json:"pick_start_hover_delay"`
	LockDelay           int      `json:"pick_start_lock_delay"`
	LockEnd             int      `json:"pick_end_lock_delay"`
	BanHoverDelay       int      `json:"ban_start_hover_delay"`
	BanLockDelay        int      `json:"ban_start_lock_delay"`
	BanLockEnd          int      `json:"ban_end_lock_delay"`
	RecentChampions     []string `json:"recent_champions"`
	RecentBans          []string `json:"recent_bans"`
}

func Defaults() Settings {
	return Settings{ChampName: "Unselected", ChampID: "0", BackupName: "Unselected", BackupID: "0", SecondaryName: "Unselected", SecondaryID: "0", SecondaryBackupName: "Unselected", SecondaryBackupID: "0", BanName: "Unselected", BanID: "0", AutoPick: true, AutoBan: true, AutoSave: true, HoverDelay: 10000, LockDelay: 999999999, LockEnd: 1000, BanHoverDelay: 1500, BanLockDelay: 999999999, BanLockEnd: 1000}
}
func Path() (string, error) {
	h, e := os.UserHomeDir()
	return filepath.Join(h, ".league_auto_accept", "settings.json"), e
}
func Load(path string) (Settings, error) {
	s := Defaults()
	b, e := os.ReadFile(path)
	if os.IsNotExist(e) {
		return s, nil
	}
	if e != nil {
		return s, e
	}
	e = json.Unmarshal(b, &s)
	return s, e
}
func Save(path string, s Settings) error {
	if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
		return e
	}
	b, e := json.MarshalIndent(s, "", "  ")
	if e != nil {
		return e
	}
	f, e := os.CreateTemp(filepath.Dir(path), "settings-*.tmp")
	if e != nil {
		return e
	}
	defer os.Remove(f.Name())
	if _, e = f.Write(b); e != nil {
		f.Close()
		return e
	}
	if e = f.Close(); e != nil {
		return e
	}
	return os.Rename(f.Name(), path)
}
