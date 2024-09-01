import io

import ccdexplorer_fundamentals.GRPCClient.wadze as wadze
from ccdexplorer_fundamentals.GRPCClient.CCD_Types import CCD_ContractAddress
from ccdexplorer_fundamentals.enums import NET
from ccdexplorer_fundamentals.GRPCClient import GRPCClient
from ccdexplorer_fundamentals.mongodb import Collections, MongoTypeInstance
from ccdexplorer_fundamentals.tooter import Tooter
from pymongo import DeleteOne, ReplaceOne
from pymongo.collection import Collection
from rich.console import Console

from .utils import Utils as _utils

console = Console()


class Instance(_utils):
    def get_module_metadata(
        self, net: NET, block_hash: str, module_ref: str
    ) -> dict[str, str]:
        self.grpcclient: GRPCClient
        ms = self.grpcclient.get_module_source(module_ref, block_hash, net)

        if ms.v0:
            bs = io.BytesIO(bytes.fromhex(ms.v0))
        else:
            bs = io.BytesIO(bytes.fromhex(ms.v1))

        try:
            module = wadze.parse_module(bs.read())
        except Exception as e:
            tooter_message = (
                f"{net}: New module get_module_metadata failed with error  {e}."
            )
            self.send_to_tooter(tooter_message)
            return {}

        results = {}
        if "export" in module.keys():
            for line in module["export"]:
                split_line = str(line).split("(")
                if split_line[0] == "ExportFunction":
                    split_line = str(line).split("'")
                    name = split_line[1]

                    if name[:5] == "init_":
                        results["module_name"] = name[5:]
                    else:
                        method_name = name.split(".")[1] if "." in name else name
                        if "methods" in results:
                            results["methods"].append(method_name)
                        else:
                            results["methods"] = [method_name]

        return results

    async def cleanup(self):

        for net in NET:
            console.log(f"Running cleanup for {net}")
            db: dict[Collections, Collection] = (
                self.motor_mainnet if net.value == "mainnet" else self.motor_testnet
            )

            todo_instances = (
                await db[Collections.queue_todo]
                .find({"type": "instance"})
                .to_list(length=None)
            )
            for msg in todo_instances:
                if msg["activity"] == "new":
                    await self.process_new_instance(net, msg)
                if msg["activity"] == "upgraded":
                    await self.process_upgraded_instance(net, msg)

                await self.remove_todo_from_queue(net, msg)

    async def remove_todo_from_queue(self, net: str, msg: dict):
        db: dict[Collections, Collection] = (
            self.motor_mainnet if net.value == "mainnet" else self.motor_testnet
        )

        _ = await db[Collections.queue_todo].bulk_write(
            [DeleteOne({"_id": msg["_id"]})]
        )

    async def process_new_instance(self, net: str, msg: dict):
        self.motor_mainnet: dict[Collections, Collection]
        self.motor_testnet: dict[Collections, Collection]
        self.grpcclient: GRPCClient
        self.tooter: Tooter

        db_to_use = self.motor_testnet if net == "testnet" else self.motor_mainnet
        instance_ref = msg["instance_ref"]
        try:
            instance_as_class = CCD_ContractAddress.from_str(instance_ref)
            instance_info_grpc = self.grpcclient.get_instance_info(
                instance_as_class.index,
                instance_as_class.subindex,
                "last_final",
                net,
            )
            instance_info: dict = instance_info_grpc.model_dump(exclude_none=True)

            instance_info.update({"_id": instance_ref})

            if instance_info["v0"]["source_module"] == "":
                del instance_info["v0"]
                _source_module = instance_info["v1"]["source_module"]
            if instance_info["v1"]["source_module"] == "":
                del instance_info["v1"]
                _source_module = instance_info["v0"]["source_module"]

            instance_info.update({"source_module": _source_module})

        except Exception as e:
            tooter_message = f"{net}: New instance failed with error  {e}."
            self.send_to_tooter(tooter_message)
            return

        _ = await db_to_use[Collections.instances].bulk_write(
            [ReplaceOne({"_id": instance_ref}, instance_info, upsert=True)]
        )
        tooter_message = f"{net}: New instance processed {instance_ref}."
        self.send_to_tooter(tooter_message)

    async def process_upgraded_instance(self, net: str, msg: dict):
        self.motor_mainnet: dict[Collections, Collection]
        self.motor_testnet: dict[Collections, Collection]
        self.grpcclient: GRPCClient
        self.tooter: Tooter

        db_to_use = self.motor_testnet if net == "testnet" else self.motor_mainnet

    
        instance_as_class = await db_to_use[Collections.instances].find_one({"_id": msg["address"]})
        if instance_as_class:
            instance_as_class = MongoTypeInstance(**instance_as_class)
        else:
            tooter_message = f"{net}: Instance {msg["address"]} to be upgradded could not be found."
            self.send_to_tooter(tooter_message)
            return    

        
        instance_as_class.source_module = msg["to_module"]
        if instance_as_class.v0:
            instance_as_class.v0.source_module = msg["to_module"]
        elif instance_as_class.v1:
            instance_as_class.v1.source_module = msg["to_module"]
    
            
        _ = await db_to_use[Collections.instances].bulk_write(
            [ReplaceOne({"_id": msg["address"]}, instance_as_class.model_dump(exclude_none=True), upsert=True)]
        )
        tooter_message = f"{net}: Instance processed {msg["address"]} upgraded from module {msg["from_module"]} to module {msg["to_module"]}."
        self.send_to_tooter(tooter_message)
