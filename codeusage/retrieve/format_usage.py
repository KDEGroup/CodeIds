from .find_usage import IdInfoUsages
from collections import defaultdict
from codeusage.build_db import Doc
from .common import IdUsages

def format_usage(
    id_info_usages_list: list[IdInfoUsages]
) -> tuple[list[str], list[IdUsages]]:
    pass
    codes: list[str] = []
    id_usages_list: list[IdUsages] = []
    parent_class_to_id: dict[str, list[IdInfoUsages]] = defaultdict(lambda: [])
    indent = 4
    for id_info_usages in id_info_usages_list:
        id_usages_list.append(IdUsages(
            id=id_info_usages.id_info.id_name,
            usages=id_info_usages.usages
        ))
        parent_class_name = "None"
        definition = id_info_usages.id_info.definition
        if definition.parent_name is not None:
            parent_class_name = definition.parent_name
        parent_class_to_id[parent_class_name].append(id_info_usages)
    for parent_class_name, id_info_usages_same_parent in parent_class_to_id.items():
        if parent_class_name != "None":
            tmp_strs = [f"class {parent_class_name}"]
            single_indent = " " * indent
            init_things: list[str] = []
            for id_info_usages in id_info_usages_same_parent:
                if id_info_usages.id_info.definition.is_in_init:
                    init_things.append(id_info_usages.id_info.definition.definition_stmt)  
                else:
                    tmp_strs.append(single_indent + id_info_usages.id_info.definition.definition_stmt)
            if len(init_things) > 0:
                tmp_strs.append(single_indent + "__init__():")
            for it in init_things:
                tmp_strs.append(single_indent * 2 + it)
            codes.append("\n".join(tmp_strs))
        else:
            for id_info_usages in id_info_usages_same_parent:
                codes.append(id_info_usages.id_info.definition.definition_stmt)
    return codes, id_usages_list
    
