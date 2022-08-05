import typing
import time

from lxml import etree
from qmonus_net_faker.application import plugin


async def setup(ctx: plugin.Context) -> plugin.Handler:
    """setup function must return handler instance"""
    return JunosHandler()


class JunosHandler(plugin.Handler):
    ################################################################################
    # NETCONF Example
    ################################################################################
    async def netconf_hello_message(self, ctx: plugin.Context) -> plugin.Response:
        response = ctx.request.netconf.create_hello_message()
        return response

    async def handle_netconf(self, ctx: plugin.Context) -> plugin.Response:
        stub = ctx.stub
        stub_repo = ctx.stub_repo
        rpc = ctx.request.netconf.rpc
        protocol_operation = ctx.request.netconf.protocol_operation

        if protocol_operation in ("get-config", "get", "validate"):
            rpc_reply = await ctx.netconf_service.execute(stub=stub, rpc=rpc)
        elif protocol_operation in (
            "edit-config",
            "discard-changes",
            "commit",
            "lock",
            "unlock",
        ):
            rpc_reply = await ctx.netconf_service.execute(stub=stub, rpc=rpc)
            await stub_repo.save(stub)
        elif protocol_operation == "commit-configuration":
            # Junos proprietary netconf.
            xml = rpc.xpath("./*")[0]
            xml.tag = xml.tag.replace("commit-configuration", "commit")
            rpc_reply = await ctx.netconf_service.execute(stub=stub, rpc=rpc)
            await stub_repo.save(stub)
        elif protocol_operation == "get-interface-information":
            # Reply to 'show interfaces fxp0 terse' request
            interface_info_xml = rpc.xpath(
                "./*[local-name()='get-interface-information']"
            )[0]
            interface_name_xml = interface_info_xml.xpath(
                "./*[local-name()='interface-name']"
            )[0]
            terse_xml = interface_info_xml.xpath("./*[local-name()='terse']")

            if terse_xml:
                if interface_name_xml.text == "fxp0":
                    rpc_reply = f"""
                        <rpc-reply message-id="{ctx.request.netconf.message_id}">
                        <interface-information style="terse">
                            <physical-interface>
                            <name>
                                fxp0
                            </name>
                            <admin-status>
                                up
                            </admin-status>
                            <oper-status>
                                up
                            </oper-status>
                            <logical-interface>
                                <name>
                                fxp0.0
                                </name>
                                <admin-status>
                                up
                                </admin-status>
                                <oper-status>
                                up
                                </oper-status>
                                <filter-information>
                                </filter-information>
                                <address-family>
                                <address-family-name>
                                    inet
                                </address-family-name>
                                <interface-address>
                                    <ifa-local emit="emit">
                                    192.168.151.211/24
                                    </ifa-local>
                                </interface-address>
                                </address-family>
                            </logical-interface>
                            </physical-interface>
                        </interface-information>
                        </rpc-reply>
                    """
                else:
                    rpc_reply = ctx.netconf_service.create_rpc_error_reply(
                        message_id=ctx.request.netconf.message_id,
                        message=f"device {interface_name_xml.text} not found",
                    )
            else:
                rpc_reply = ctx.netconf_service.create_rpc_error_reply(
                    message_id=ctx.request.netconf.message_id,
                    message=f"'terse' not specified",
                )
        else:
            rpc_reply = ctx.netconf_service.create_rpc_error_reply(
                message_id=ctx.request.netconf.message_id,
                message=f"Invalid protocol operation: '{protocol_operation}'",
            )

        response = ctx.request.netconf.create_response(rpc_reply)
        return response

    ################################################################################
    # HTTP Example
    ################################################################################
    async def handle_http(self, ctx: plugin.Context) -> plugin.Response:
        body = "<ok/>"
        response = ctx.request.http.create_xml_response(code=200, body=body)
        return response

    ################################################################################
    # SNMP Example
    ################################################################################
    async def handle_snmp(self, ctx: plugin.Context) -> plugin.Response:
        stub = ctx.stub
        stub_repo = ctx.stub_repo

        # Reset
        stub.delete_all_snmp_objects()

        # Set sysUpTime
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.1.3.0",
            type="TIMETICKS",
            value=int(time.time()) % 4294967296,
        )
        # Set ifIndex
        stub.set_snmp_object(oid="1.3.6.1.2.1.2.2.1.1.1", type="INTEGER", value=1)
        stub.set_snmp_object(oid="1.3.6.1.2.1.2.2.1.1.2", type="INTEGER", value=2)
        stub.set_snmp_object(oid="1.3.6.1.2.1.2.2.1.1.3", type="INTEGER", value=3)
        # Set ifDesc
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.2.2.1.2.1", type="OCTET_STRING", value="fxp0"
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.2.2.1.2.2", type="OCTET_STRING", value="xe-0/0/0"
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.2.2.1.2.3", type="OCTET_STRING", value="xe-0/0/1"
        )
        # Set ifName
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.1.1", type="OCTET_STRING", value="fxp0"
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.1.2", type="OCTET_STRING", value="xe-0/0/0"
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.1.3", type="OCTET_STRING", value="xe-0/0/1"
        )
        # Set ifHCInOctets
        stub.set_snmp_object(oid="1.3.6.1.2.1.31.1.1.1.6.1", type="COUNTER64", value=10)
        stub.set_snmp_object(oid="1.3.6.1.2.1.31.1.1.1.6.2", type="COUNTER64", value=20)
        stub.set_snmp_object(oid="1.3.6.1.2.1.31.1.1.1.6.3", type="COUNTER64", value=30)
        # Set ifHCOutOctets
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.10.1", type="COUNTER64", value=40
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.10.2", type="COUNTER64", value=50
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.10.3", type="COUNTER64", value=60
        )
        # Set ifHighSpeed
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.15.1", type="GAUGE32", value=1000
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.15.2", type="GAUGE32", value=10000
        )
        stub.set_snmp_object(
            oid="1.3.6.1.2.1.31.1.1.1.15.3", type="GAUGE32", value=10000
        )

        # Save
        await stub_repo.save(stub)

        objects = await ctx.snmp_service.execute(
            stub=stub,
            pdu_type=ctx.request.snmp.pdu_type,
            objects=ctx.request.snmp.objects,
            non_repeaters=ctx.request.snmp.non_repeaters,
            max_repetitions=ctx.request.snmp.max_repetitions,
        )

        response = ctx.request.snmp.create_response(objects=objects)
        return response

    ################################################################################
    # SSH Example
    ################################################################################
    async def ssh_login_message(self, ctx: plugin.Context) -> plugin.Response:
        stub = ctx.stub
        output = (
            "Last login: Fri Feb  1 00:00:00 2021 from 10.0.0.1\n"
            "--- JUNOS Dummy Kernel 64-bit Dummy\n"
        )
        prompt = f"{ctx.request.ssh.username}@{stub.description}> "
        state: dict[typing.Any, typing.Any] = {}
        response = ctx.request.ssh.create_response(
            output=output,  # output message
            prompt=prompt,  # prompt
            state=state,  # session storage
        )
        return response

    async def handle_ssh(self, ctx: plugin.Context) -> plugin.Response:
        state = ctx.request.ssh.state
        input = ctx.request.ssh.input
        prompt = ctx.request.ssh.prompt

        if input == "":
            output = "\n"
        elif input.startswith("set cli complete-on-space off"):
            output = "Disabling complete-on-space\n\n"
        elif input.startswith("set cli screen-length 0"):
            output = "Screen length set to 0\n\n"
        elif input.startswith("set cli screen-width 511"):
            output = "Screen width set to 511\n\n"
        elif input.startswith("show configuration | display set | save ftp"):
            output = (
                "ftp://username:password@10.0.0.1/  100% of 680 B 1024 kBps\n"
                "Wrote 20 lines of output to 'ftp://username:password@10.0.0.1/file.conf'\n\n"
            )
        else:
            output = "\nunknown command.\n\n"

        response = ctx.request.ssh.create_response(
            output=output,  # output message
            prompt=prompt,  # prompt
            state=state,  # session storage
        )
        return response

    ################################################################################
    # TELNET Example
    ################################################################################
    async def telnet_login_message(self, ctx: plugin.Context) -> plugin.Response:
        output = ""
        prompt = "login: "
        state = {"phase": "USERNAME"}
        response = ctx.request.telnet.create_response(
            output=output,  # output message
            prompt=prompt,  # prompt
            state=state,  # session storage
        )
        return response

    async def handle_telnet(self, ctx: plugin.Context) -> plugin.Response:
        input = ctx.request.telnet.input
        state = ctx.request.telnet.state
        stub = ctx.stub

        if state["phase"] == "USERNAME":
            output = ""
            prompt = "Password: "
            state["phase"] = "PASSWORD"
            state["username"] = input
        elif state["phase"] == "PASSWORD":
            output = (
                "Last login: Fri Feb  1 00:00:00 2021 from 10.0.0.1\n"
                "--- JUNOS Dummy Kernel 64-bit Dummy\n"
            )
            prompt = f"{state['username']}@{stub.description}> "
            state["phase"] = "OPERATION_MODE"
        elif state["phase"] == "OPERATION_MODE":
            if input == "":
                output = "\n"
            elif input.startswith("show configuration | display set | save ftp"):
                # Copy config to ftp server
                output = (
                    "ftp://username:password@10.0.0.1/  100% of 680 B 1024 kBps\n"
                    "Wrote 20 lines of output to 'ftp://username:password@10.0.0.1/file.conf\n\n"
                )
            else:
                output = "\nunknown command.\n\n"
            prompt = f"{state['username']}@{stub.description}> "
        else:
            raise Exception("Undefined phase state")

        response = ctx.request.telnet.create_response(
            output=output,  # output message
            prompt=prompt,  # prompt
            state=state,  # session storage
        )
        return response
