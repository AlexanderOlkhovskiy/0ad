#ifndef SCENARIOEDITOR_H__
#define SCENARIOEDITOR_H__

#include "General/AtlasWindowCommandProc.h"
#include "SectionLayout.h"

class ScenarioEditor : public wxFrame
{
public:
	ScenarioEditor(wxWindow* parent);
	void OnClose(wxCloseEvent& event);
	void OnTimer(wxTimerEvent& event);
	void OnIdle(wxIdleEvent& event);
	
// 	void OnNew(wxCommandEvent& event);
	void OnOpen(wxCommandEvent& event);
	void OnSave(wxCommandEvent& event);
	void OnSaveAs(wxCommandEvent& event);

	void OnQuit(wxCommandEvent& event);
	void OnUndo(wxCommandEvent& event);
	void OnRedo(wxCommandEvent& event);

	void OnWireframe(wxCommandEvent& event);
	void OnMessageTrace(wxCommandEvent& event);
	void OnScreenshot(wxCommandEvent& event);

	static AtlasWindowCommandProc& GetCommandProc();

	static float GetSpeedModifier();

private:
	wxTimer m_Timer;

	SectionLayout m_SectionLayout;

	void SetOpenFilename(const wxString& filename);
	wxString m_OpenFilename;

	DECLARE_EVENT_TABLE();
};

#endif // SCENARIOEDITOR_H__
