import pydantic2zod
from pydantic2zod.model import BuiltinType, ClassDecl


class Compiler(pydantic2zod.Compiler):

    def _modify_models(self, pydantic_models: list[ClassDecl]) -> list[ClassDecl]:
        for model in pydantic_models:
            if model.name == "Item":
                for f in model.fields:
                    # In pydantic declarations Product.description is optional.
                    # Lets make it required in zod.
                    if f.name == "description":
                        f.type = BuiltinType(name="str")

        return pydantic_models


ts_src = Compiler().parse("skellycam.core.frames.payloads.frontend_image_payload").to_zod()
print(ts_src)
