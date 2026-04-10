local file_path = ...

if file_path == nil or file_path == "" then
	error("expected a path to a .rbxl or .rbxm file")
end

local function infer_format(path)
	local extension = string.match(string.lower(path), "%.([^.]+)$")
	if extension == "rbxl" or extension == "rbxm" then
		return extension
	end

	error("unsupported binary Roblox extension: " .. tostring(extension))
end

local script_classes = {
	Script = true,
	LocalScript = true,
	ModuleScript = true,
}

local instances = {}
local next_id = 0

local function serialize_instance(instance, parent_id)
	next_id = next_id + 1
	local current_id = next_id
	local properties = {
		Name = instance.Name,
	}

	if script_classes[instance.ClassName] then
		local ok, source = pcall(function()
			return instance.Source
		end)
		if ok and source ~= nil then
			properties.Source = source
		end
	end

	table.insert(instances, {
		id = current_id,
		class_name = instance.ClassName,
		parent_id = parent_id,
		properties = properties,
	})

	for _, child in ipairs(instance:GetChildren()) do
		serialize_instance(child, current_id)
	end
end

local function serialize_root(root)
	if type(root) == "userdata" then
		if root.ClassName == "DataModel" then
			for _, child in ipairs(root:GetChildren()) do
				serialize_instance(child, nil)
			end
			return
		end

		serialize_instance(root, nil)
		return
	end

	if type(root) == "table" then
		for _, child in ipairs(root) do
			serialize_instance(child, nil)
		end
		return
	end

	error("unsupported decoded root value type: " .. type(root))
end

local bytes = fs.read(file_path, "bin")
local decoded = rbxmk.decodeFormat(infer_format(file_path), bytes)
serialize_root(decoded)
print(rbxmk.encodeFormat("json", {
	instances = instances,
}))
