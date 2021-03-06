const g_TechnologyPath = "simulation/data/technologies/";
const g_AuraPath = "simulation/data/auras/";

var g_TemplateData = {};
var g_TechnologyData = {};
var g_AuraData = {};

// Must be defined after g_TechnologyData object is declared.
const g_AutoResearchTechList = findAllAutoResearchedTechs();

function loadTemplate(templateName)
{
	if (!(templateName in g_TemplateData))
	{
		// We need to clone the template because we want to perform some translations.
		var data = clone(Engine.GetTemplate(templateName));
		translateObjectKeys(data, ["GenericName", "SpecificName", "Tooltip"]);

		if (data.Auras)
			for (let auraID of data.Auras._string.split(/\s+/))
				loadAuraData(auraID);

		g_TemplateData[templateName] = data;
	}

	return g_TemplateData[templateName];
}

function loadTechData(templateName)
{
	if (!(templateName in g_TechnologyData))
	{
		let data = Engine.ReadJSONFile(g_TechnologyPath + templateName + ".json");
		translateObjectKeys(data, ["genericName", "tooltip", "description"]);

		g_TechnologyData[templateName] = data;
	}

	return g_TechnologyData[templateName];
}

function loadAuraData(templateName)
{
	if (!(templateName in g_AuraData))
	{
		let data = Engine.ReadJSONFile(g_AuraPath + templateName + ".json");
		translateObjectKeys(data, ["auraName", "auraDescription"]);

		g_AuraData[templateName] = data;
	}

	return g_AuraData[templateName];
}

function findAllAutoResearchedTechs()
{
	let techList = [];

	for (let filename of Engine.BuildDirEntList(g_TechnologyPath, "*.json", true))
	{
		// -5 to strip off the file extension
		let templateName = filename.slice(g_TechnologyPath.length, -5);
		let data = loadTechData(templateName);

		if (data && data.autoResearch)
			techList.push(templateName);
	}

	return techList;
}

function deriveModifications(techList)
{
	let techData = [];
	for (let techName of techList)
		techData.push(GetTechnologyBasicDataHelper(loadTechData(techName), g_SelectedCiv));

	return DeriveModificationsFromTechnologies(techData);
}

/**
 * This is needed because getEntityCostTooltip in tooltip.js needs to get
 * the template data of the different wallSet pieces. In the session this
 * function does some caching, but here we do that in loadTemplate already.
 */
function GetTemplateData(templateName)
{
	var template = loadTemplate(templateName);
	return GetTemplateDataHelper(template, null, g_AuraData, g_ResourceData, g_CurrentModifiers);
}

/**
 * Determines and returns the phase in which a given technology can be
 * first researched. Works recursively through the given tech's
 * pre-requisite and superseded techs if necessary.
 *
 * @param {string} techName - The Technology's name
 * @return The name of the phase the technology belongs to, or false if
 *         the current civ can't research this tech
 */
function GetPhaseOfTechnology(techName)
{
	let phaseIdx = -1;

	if (basename(techName).startsWith("phase"))
	{
		phaseIdx = g_ParsedData.phaseList.indexOf(GetActualPhase(techName));
		if (phaseIdx > 0)
			return g_ParsedData.phaseList[phaseIdx - 1];
	}

	if (!g_ParsedData.techs[g_SelectedCiv][techName])
	{
		let techData = loadTechnology(techName);
		g_ParsedData.techs[g_SelectedCiv][techName] = techData;
		warn("The \"" + techData.name.generic + "\" technology is not researchable in any structure buildable by the " +
			g_SelectedCiv + " civilisation, but is required by something that this civ can research, train or build!");
	}

	let techReqs = g_ParsedData.techs[g_SelectedCiv][techName].reqs;
	if (!techReqs)
		return false;

	for (let option of techReqs)
		if (option.techs)
			for (let tech of option.techs)
			{
				if (basename(tech).startsWith("phase"))
					return tech;
				if (basename(tech).startsWith("pair"))
					continue;
				phaseIdx = Math.max(phaseIdx, g_ParsedData.phaseList.indexOf(GetPhaseOfTechnology(tech)));
			}
	return g_ParsedData.phaseList[phaseIdx] || false;
}

function GetActualPhase(phaseName)
{
	if (g_ParsedData.phases[phaseName])
		return g_ParsedData.phases[phaseName].actualPhase;

	warn("Unrecognised phase (" + techName + ")");
	return g_ParsedData.phaseList[0];
}

function GetPhaseOfTemplate(template)
{
	if (!template.requiredTechnology)
		return g_ParsedData.phaseList[0];

	if (basename(template.requiredTechnology).startsWith("phase"))
		return GetActualPhase(template.requiredTechnology);

	return GetPhaseOfTechnology(template.requiredTechnology);
}
