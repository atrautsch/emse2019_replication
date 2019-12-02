
import re
import glob
import os
import subprocess
import shutil

from lxml import etree
from shutil import copyfile

from util.pmd import PMD_NAME_TO_SM, PMD_OLD_RULESETS, DEFAULT_RULES_MAVEN_CLEANED


class MavenError(Exception):

    def __init__(self, output):
        self.output = output
        self.type = 'unknown'
        self.line = ''

        error_types = {
            'unknown': None,
            'parse': 'Non-parseable POM',
            'parent': 'Non-resolvable parent POM for',
            'malformed': 'Malformed POM',
            'buildext': 'Unresolvable build extension',
            'child': 'Child module',
        }

        for k, v in error_types.items():
            if v and v in output:
                self.type = k

        for line in output.split('\n'):
            if error_types[self.type] and error_types[self.type] in line:
                self.line = line

        super().__init__('mvn help:effective-pom error')

# extracted from errors thrown with pom.xml not found, opennlp changed the pom location from /pom.xml to /opennlp/pom.xml in this commits.
OPENNLP_REVISION_POM_WRONG_PATH = ['8c0bf6de657f122d902283d3f1a1e3e10df9c594', 'cfa110799b8709f064fc6712f746cb84f1b9f290', 
'd03b072591b3f3c3d0dd4f632fd40a56eefdf61c', '4bb7a600e662ea31ab6f2e46d86670d9363aee48', '35544c516b73c8e8135854ba8aedeefa62a12b17', 
'e8ce1cb366ee86fc5b735c0e17cad67be2e1ab10', '84b1b66e84411fd937fdc552a88b3e428efd4c5c', '26e920edff81af24c82ecb23d1a80126fde84695', 
'f327462173cc1ef58c951e473248c2fa0e81dc52', 'a7679f509cf0492c43367ad28b98588ab40f4b56', 'e96c430ccf8e58e9e81dac62e657811c744d04c2', 
'f8833ce58264603144a81acb7d60193f270b4e39', '3b04dccc1c28fde53a283fae7b1bce5879d20aef', '7e9614e0c615a62be67a4f26a68377adcc01f44a', 
'4875db7b9c81c0367cb57c76130f6b2219acbbd8', 'e6dbd4f68627658da2d845776ec497afbbc070d5', '57aec26093b43653786f8927680e4188733a372b', 
'b98e26d1c55e2f94cf9b600902422af9dd552836', 'b9461e549d8ff64b772c7df8640699f580dd6e0c', '496bebe99447f459902c559776b505df9bfd349e', 
'544c2112a9b741e670ea73be0392a243fa22881f', 'b4430d9c385eb5e9e64047ac37bdc8c7aa4ffa40', 'e584bc9159fbc0fcd6585c256ce67cd9c9f2f990', 
'34c0eec1c4b042bfaf9c589ca62de579b528cb45', '22125a10bf035eff104f154161891aa6e75dee40', '9b9d44b77b9b0a0721b333498ddf0514e0e3e212', 
'b3b063880447834d63d1b281913cde67057df716', 'c1871723452f6f3b2b271cc11d244ed19498d6e9', '0b3f6c24a6e6039f9065935e2893aa3b287c3672', '0961dc9a58174c05667cd820580e402680779573', '862108ce4329d1d3664b270891ba3f68fec63a28', '112ea738148f1371a18b2a4d78f577bcc395c430', '85fa224ce8190e2b2831107ef0c87f90924c39a2', 'c2bc1b12f71187bce22b4118c227aeedacb3df98', 'fcbe040e1c56d5e633c01b3808fe8779ee902286', 'a30d918dbc7e9eaf74fc4927d4f66fbfe145003c', '09547be889e53230ee8846d2f76f82d6c7e8e9fa', '8fe63ab79581d58b1202677270d20d81fa73f950', '1f6e4de041d2c2f3e22ad317a4df1965872bdbea', '0aa13043f24d961a1f36c608347361e136fc6e53', 'cc915ef0b7af5d8f694aeebb26b445549e89e06e', '78ff264ab7e10fa60b579d15f0b464026228a4d0', '5b9ed7fac3d3897c0bd8768c36a2ded73ada2c92', '0ad020328b04b89750fd104c455d6b7469d4e187', '88d8f7a6a9ea586dee398de5485cc85024445f90', 'd90b1af31a89d2891746f6b873b5db74aead786a', 'ea6e91ce6061895d8818de085161adc6e814151f', 'ac88b1b2d106a15f59fb65fa653816bea22d8d34', '8fe332cd85086a73908576b2a45d43fc7c188308', '197eeea2c6bb0e829cfc899c21f4509134ab4b9c', 'b74695ee7dc943af9123a43bd7de2a5c40307985', 'ca1ce17a78bc3c2aad4868bffed66c11b4845205', '89f95b18996e44977d7eeda10c23647e2cd61cad', '8ae8428df5da99e5d416633be625bd8c848659ce', '79aa27070d32c6ab226809d953570ff055406284', 'db779efb02f02483187254398d9fe3d00dc9a37c', 'b2f6bd96ae4341c223ec00ec2a4740b5492d74b3', '0b4298d2c578bc8e0b51aaf07755a435c52a8fca', '1898c6913820a9a06c2c5a516b0f856ca3cbf580', '88389a50e02e94315bb5249f8725e34ac4e6922d', '0c13d8af026936be14e4e9353838d785b11411f6', '40d023c3a15996cd1628c776e6f5103969b5066a', '999248dbd2699a9fe2854304d2c8a8f79b313431', '8d1e01462a24bc28cc24ab44b13d7c698cd39829', '0ecde6a54c76574bc91d267715fe041a5f6dfa05', 'c54705098cd19fb7363bae98c8e0b71e497dc1e5', '18fbfbf41e53018f1b3fe460344f10b2e01d9186', 'd8e7cc9a6eb0fd2f1ec49e7ade1051326060945e', 'f708f27afae3565e47e5fb4a2ff79e50dd1e268f', '07dcb1fc499b3db4d29f877748fee2aa5615ebba', '2fe5f10941a888e9e14bc0357d6537f8408ba3bb', '7aa4f66e828b36592543f0d2738547cb7c25159e', '369a17c60c5a77b2e962156355a3bd4927232729', '2b7e493267cd755379570b6ca976ae9249c69d8f', '17e5b3b2e10c674658cd223e1f087958dba41f76', '779e7542f7df3e1c0da7e75b721c7351af250eb6', '1a5adba469874b382c9fd1ca10e70edcade5cf05', '0750dd0a4d1fee6e1b264d20c5a91027357651ff', 'acd371a3a7d2fe9b834abd1bd0f236df95852531', '5d00326de42cc9c91e92c92ff4eac6f8463da090', '6ad8dd56f6af1dec248d9db7e11762fbf092600c', 'bc49c600ed9ff9991020cd8de1fd9fb552491076', '23ca5dd2d942c9b3f703e9fc802119c8756e77b7', '37b4d2a143e4dd30a9c6afbbca9e154275e00195', 'bc361560af32eff947afe5154d5dc66b2a1fd370', '7e5a024ccd922903070a420ee71299202370cc48', '0aa15315482ce0fe16e4f8d93ecc5200fd59d350', '68fe1b1ade0350ea05be23e960c722acd2eb4155', '3a2db3b71e9c6372972b03a24677b02f8dbab7f8', 'f93ede3aafa2001c78175486a1c8e6c222932df6', 'dd424ff9f1affb40da4909d4f6c7c4aaf380e0a1', 'a789ac3dc2b110fb76dae58062dc5f90bf6401e3', '2dc3163abe88a7083695f167aca7a48ca9cae60a', '5b30f738a76a2f4aa4c5e5a4c448bca3d850dc23', '224e1c66cbf2507a2d6fd32d37a4c08806efb40f', '0c9ce07af26c9fd0b78fdefc78d9944999da4195', '2be36adfbb96cef8ead81957e25deccfe0b0718c', 'f12f0eafdfe7260fa4a551d31723a50d8d2c5f73', '4b76645f0691ff6474fdf9a0124a64b4a0974832', '70905a8335e2c20e0ca8265fc28197fae798a171', '2966a5a910b903d91ece62750b8d7457f144eeca', '7139ffd4fb40484a57ae647dde0aa437ba71e116', '80cc598e4776f03a42fcfaa279036999465b0aee', '68e1a4edd37e771c76bb43ef762d927833cb1174', '1db799b871285c473a596b5416baecf94dcbc0a0', '106ca755402e333409a77b988fd02f5218eea2c5', '6332d419da5a43bb5cdbf8b9d5e93944f94ab951']

CUSTOM_PATHS = {'mahout': {'../buildtools/src/main/resources/mahout-pmd-ruleset.xml': 
                                {'new_file': 'buildtools/src/main/resources/mahout-pmd-ruleset.xml', 
                                 'revisions': ['5681bb0f11e29897635456c43603605169010ecf',
                                               '229aeff334882293c915b27e40a4864878a644b9',
                                               '46ed1c07f3606df8e3d47ca3531c07b03911659d']},
                           '../eclipse/src/main/resources/mahout-pmd-ruleset.xml': {
                                'new_file': 'eclipse/src/main/resources/mahout-pmd-ruleset.xml',
                                'revisions': ['f1ca6dee7fd0ce189b250eaf01b475847c19ffda',
                                              'e1136b9f97ad5dabf3c0251a06487d0e84eebb74',
                                              '1626b4cbe0991c15147fd8796ac0b41111642ae1',
                                              'c242e523dcb20dc9585580bfc5d8b459217160fd',
                                              'abff05e2a13cb88d4d4628062d2bbf02df058b08',
                                              '50fd693770212294b1c14eb9ec10324c7d99a303']
                           },
                           '../maven/src/main/resources/mahout-pmd-ruleset.xml': {
                                'new_file': 'maven/src/main/resources/mahout-pmd-ruleset.xml',
                                'revisions': ['0357f87ef42f892640f3c020980b34d5424f7ce8'],
                           },
                           '/mahout-pmd-ruleset.xml': {
                                'new_file': 'buildtools/src/main/resources/mahout-pmd-ruleset.xml',
                                'revisions': ['d9d24d35952292a9fb4761676192ea7fa4a8fdc9',
                                              '34bf3badcffa171524cd343e81827134076b8911',
                                              '279c2bcc8015aaa1d192e01274d5066b496a39ac',
                                              '3f973d6460fc0ec239d13b6ebfb1f7054f359fe2',]
                           },
                           'mahout-pmd-ruleset.xml': {
                                'new_file': 'buildtools/src/main/resources/mahout-pmd-ruleset.xml',
                                'revisions': ['cd13dfd89072713c491edd0b61e9461f04396f32',
                                              '02ecad17bac6be42eb946fcc029d10dda283b57c',
                                              '13b793cccf3662c7f5289bc383dccbede0e12aed',
                                              '1a42d852daa75cf9b6a78013544647be2ec2a8e3',
                                              'bae0d6e11bc4ac19beebba85b1670dcb4be3e3df',
                                              '1f17d23f6095e67a2f8d188f4817e286cf916e98',
                                              'b988c493b562ceeaa5f82027f108c67d06c1fc19',
                                              '1cfa8eab6b2aaa8e01e7ac162926ed3fbc6fe44d',
                                              'b391c76502a5294284fe761de86f952fd91434a5',
                                              '034790cce40fcee2b7a875c482345d35f7c0fa8d',
                                              'f8596b8668ca5104a28efd54d0ceaab51a619c89',
                                              '5afdc68e0a25e9f66a0d707a7f76d46d9603b614',
                                              'f2f8cba4279b86b3a902fcac27e6f5db1d1e49ba',
                                              '0f82e09527150753901ea0deeb2fcec8d45de781',
                                              'df08a37c4112cbe1161f5c20f985e9c1c9abff42',
                                              '2f55adeffebef2fdd1295deb1c44489d33b0b495',
                                              '7f8418365775dbfac768e5cf2371b00bd9976581'
                                              ]
                           },
                           'src/main/resources/mahout-pmd-ruleset.xml': {
                                'new_file': 'maven/src/main/resources/mahout-pmd-ruleset.xml',
                                'revisions': ['97033e3b1964ad1da319f72fe8874333dc487245',
                                              'a435efb1a63b8530bdf120ba9965f33fda9db92f',
                                              '49bb59b3654d4e4803f966bd162d20f0f5d720ff',
                                              'ebf9a4d9c26c182c26d5fdb3ea4b1f12ed19a7bb',
                                              '1b16a94949af5564cd35a530b06ded5f6234fc28',
                                              'c0b74781eb165ff410e953d844da9c00dabac235']
                           }
                        },
                    'wss4j': {'wss4j-pmd-ruleset.xml': {
                        'new_file': 'build-tools/src/main/resources/wss4j-pmd-ruleset.xml',
                        'revisions': ['4b6f3a596be0e19c7ef13b5e973491bec80c8f8c', 'd1a9c7c77d75c2c299f2bd41ebcc3c27c95fba1d']
                    }},
                }

# provides mapping to custom pom.xml names
CUSTOM_POM_NAMES = {'commons-io': {'project.xml': ['c801bc302edb61a937f58dafbfbc36e1c0f021cf', '64b5ec2aa8e02859c1a1cc7fa3c986aa20f45b4b', '4b1b80c2cc232fb6e70a4a6fe7058180e9ab2728']},
                    'commons-dbcp': {'project.xml': ['bf1169938c2b0abf933cba23657bb428ad51da69', 'ce2c3b60cf60e3c71bbcefab258096f181f3b19d', '8cd8313e29171c32d75c77943e61c231affed9eb', '6727f18d8e1a6ac183ac7015fa16579fce0791ed']},
                    'commons-lang': {'project.xml': ['3c712f6fbbfcc5478c87e12bb3a458377834727b', 'f58370a13fb6e8c3f4a04233fab5ebd4e8027778', '73c82134a1c9d6e679c8045243d3756bc96f6c7c', '5e18fd65ff211107190d8158977091fd7c033776', '513d12877388300d4e0dd2b808448b7e3f95d785', 'a5a4f9067a0b22e629463b1ef059818ccda6f37e']},
                    'commons-compress': {'project.xml': ['ad894fa864290bf7588f752837d65e901ae99b76', 'ceead0b7213c5543fded341078715fc56e94848f']},
                    'commons-codec': {'project.xml': ['c5ddea546bdce2a07adcb961878c881261136b6b', 'c1b1a1ffca322edf9af7689f40d5ae3e0e889661', '2c53a487a8c171c7a9962d7eaada48c245f58352', 'ec58c0159567baa3407739aad273dd1f22c9c98b', '0f9ad2ebc9f566960829716fde8953acae5993f1', '3f9fa6d1c49995de28209c5525fa11a3a3f97b9b', '15194a9e772c4929ff008333d3537221095d6237']},
                    'commons-jcs': {'project.xml': ['763c4bbf42e4e65a6c7833a6a904c5dad5be6da6', 'c6f97c5bcc748a11d65899c375637d510d37381e', 'a885a5638827c095c260d585b05b67c19bc450ac']},
                    'commons-digester': {'project.xml': ['6805238a9dbe79c0ada3d330cb06122d9662cef2', 'e58a379843c39a5aafb6925f913e79388adeb406', '469eb7da0dabd07c101e0595c0001a646c8be634', '3b8978249b76c791685939068ad6221b54db3d07', '9f7ff52ca2a44be87beb73cd0df9b77c63da742a', 'ab9a839ad397af939dd62779bb58922d370a25d6', '190c61c69027578a00a85a3e612236f460b8bf05']},
                    'commons-math': {'project.xml': ['e449062da5090d3ab56b2f5d20bc74b802f03fe4', 'ffa6aac264f1662907f1655b791df7aa2b38d411', 'e389289e779612c5930d7c292bbbc94027695ae5', 'a58c503cf5b0f02ad442e3e473dc032e0e26eee5', '94f23a61b56cc125e70004f6562a0895a0613dd6', '4952dd85d66701c5e079303f163baba5a2fe5ce0', '86b71e2963dc643d9db646d0dedaa0b4d64b4e42', '7f8947c03c50073a886b79223783ac5762dc4237', '4dd57aafc1b1237e35372acd1866e8bff8b3ace1']},
                    'httpcomponents-core': {'project.xml': ['be05e6255871bafdcd80c390898a5c9d5385b134']},
}


# provides a manual mapping to the main pom.xml file
CUSTOM_POM_PATHS = {'manifoldcf': {'modules/framework': ['8df8a8f425d43f7f2e7c5c6af47dfd82a654fe87',
                                                         '88c7045e5994efb533aa177b9f1ca00121b86fb8'],
                                    'framework': ['30e0fc6f6202c0b3bf47ff4f8b8ae42a43e08733',
                                                  'e74938d334942da964a89ae8dc541e93a113b54d',
                                                  'bbd6a7cd0a62583239503f88391cc33fa3a61f9a'],
                                   },
                    'opennlp': {'maxent/trunk': ['6cc5c2ba2fc1dd4f51f36cee1cf6c8e353ab70f2'],
                                'opennlp-maxent/trunk/': ['e3243470b11741ff0e0cb666a81a0a9128c02d1d',
                                                          '9da1bfc6383bb9d4053c96aaeebdb63855f44a13',],
                                'opennlp-maxent': ['9cc16c9bde275c99c97d663614555af10efa228f',
                                                   'f7bbdb2377ae6edcdc6011c4d4c1cc2b4d9e65c7',
                                                   '35478414ee815a1db1c27033610b99920b667cd4',
                                                   '5c47882dd7b064006272a08154982ac93bf8ecd1',
                                                   'e5020a5dcab26f79bb04a89dea3b85e4d06b3369',
                                                   'dcc5bd6694c36530a3f6d277150153403b820fd9',
                                                   '665968fd164762bba767bc1543a91c88aa95ea9c',
                                                   ],
                                'opennlp-tools/trunk': ['4fbaf9c05c3b79f838ef77d561592780e8b5914d'],
                                'opennlp': OPENNLP_REVISION_POM_WRONG_PATH},
                    'systemml': {'SystemML/DML': ['d52086d17ac3a38a2311a51c31cf9682a884550e', '41dee209e81b019b89e9ab8a8a48f5778313f090'],
                                 'SystemML/SystemML': ['d07f9fa9f9c74adbef19b9a9164f36a325ef62d7', '5912d110f0aa91d1e5d429bb183da12e4c731a7a', 'a3ba99f8617c6a78f1ea566a46ade72c16561a2b', '034b0fa510bd925ac4f6ec145fa97265c3004e17', 'e8ba0015a40c0651bb1aafc1fdbfb0f8e2db4106', '295cc418858d30b70ebe2a4fa3e454c41232ea76', '0782080766cbeedd777c815da61fed698ec911d7', 'd842e7f912c41fa90a994c3474512a52af761db2', 'cc1197d7983644d915fdd94e856f4caf509eb81a', 'f08ad7fdf712c67441e528effe56b14126c7f254', 'eaaed009b5a82477c4607537355653ba8b83997b', 'f0429626700d52f365dab0a6e3ce0ef86036eb16', '7d1cdc4dce196859e9895b4ce432754dbf6adf79', '3dafe20350c60a335597188384636218caa8ee54', 'bbd8d16c6cf7b5586ce154d5c0a8b7690e6c7eb9', 'cd974b5080c971435859b488e4c6ef7fb7244183', '6f6c4093d4b3498bc2be0e897286b4d5deaa2365', '034783530dab8af092c41c7cf3be7cbea1c1df96', '4da890ec327f758b8285fbc85b4680aedb1c6c6d', 'd0a7ea26f675b36cc34ff862ff1042978b0e92ba', 'c42280000b9c61072b438908562507826ef40049', 'c4dfaaed4af209d4f9d18ee398cb69983f909b12', '41bc04efdfefeb05e153447cc21fbb6f6b6d7e6d', 'adacdcd198e8b5f05eaf27d0922eb42822c9e264', 'b7ce6d9eb4cdf1faf9ec7ed6830c77a75ab10aaf', 'f15836e80ee3ed243c356c4fffc6da944b7d37a6', '1fa176ade8bc072c843e1d266f7e3f4f84337b26', '243704694e1fc53f2305c2f840fdf8580ccf4268', 'a715dc51ab408d6143b3e0705cc0bd10376d88ac', '1cf90f0f0fe8b539dfcd32932fae91c48f3c5413', '99fa4ebf8730b67e7882d0f394a58b6d1545e326', '7b9fea7e320f7c57a042261575f3838dba914175', 'b37024660a040def76525af3edbae07de958b11e', '1e212bc303d41dc90cf7236938cea6191b3d63e1', '4cfc736f010041919e67aac21656d4eb1082e86f', '423a7bb311115cfdd6db5376b92326adad8edcb8', 'adefec59cb7a9db68b0424731c9b9353ab44245a', '2e5b23c0f1477e7ba19c4313c5db612f70d98df9', '7f40039a0e54e119e561b85e9b0a63445ad341cd', '59fd4f867f6697844b0052330152814e4d78e816', '9fa0abadbb5427dff54d1334668861b2e36a1f44', 'a1b0e7834318e0b64a2f0d28177eb2c71a9ce6bd', '0c79efbe73184ef8bd01bcaeff6fde0962b711f7', 'b59b1e5f7cf09fe41afeb45fd63f9a529fde9195', '2b558b5219159f667b297fc947e32c2b35fd09ef', 'aec9fd80a31b8a82324e3810841471102735549c', 'c1a6947c5dc033065d32e2fa5632e3acd99e4a47', '1cca32fab95dbdfbd72760c0efde84bfc4618a4c', '6c5c69cdf4d044430136508de39ef4235cd50140', '197fdf18ace2bacc208b207e66dd0f1d59efddd6', 'e4618ddae2ea856f6d8b8d3402d10ece5e5c99bb', '7d1e583f4eb32827fa162f290876be4b85c40d96', 'f74a8c86989a25e2cc4a6f785f79b32308e5ad58', '8a5ee7540c39d6497f0cc82bde2a0442a57066e4', 'f0ebade2971c95551a65cba2d57b8d64c3849af8', '20c7f54345468ae7faedfbfeb2e8bc9cb5d7912f', '23388b5119634b4ea59d1abeb1876c7702607703', 'd83c69264991b23349f6d3af3299271007cc37cd', 'bea54f2298a52ab000ec6594c471570cc3e980bc', 'afeb689d40154e05ca26716a5704c6cabe7f897d', 'fb232c279007d12ff9eb562248104e27ddd1d43e', '713634d6228018a210d83d802e600c3194b49b3f', '4da8feeb2e6cc12a57ff92aa550e328ab8e916ff', '6535a7c47b660921242cd6e84ac2e2ebd756ff6d', '21cab7ac32f1bdb494034dd5022dfe4528319358', '974c12eaa0b2538732330e986d943f7b0464b77d', 'b1daa0714e69ee6657574be5d12431ea5d85876a', '5b547bb258dc5d236587494daca09d0d8b10421b', '4513af2475b2e64ae22c4aa5bb2277090da26a80', 'dc95ebe3431a0022d07cc41869585b22da4ded51', 'dd2dec4276685822d1edf5f541d5a7e9498632f7', '75c51191303191d57565f0414b1fc0f6cba47f1a', '0280d11d84f07af7b933ae71a7e7a7c631258772', 'f99a5ecc43f0ca2ec96a07eeb54599c7f6563b99', '81a811b7e3f3439a3bf5598dd1d0b3f8e2486513', 'bd2170787ef49f0dd81628c85e6b585d4b7bb75d', '86a556e2f6f1e0cdb7d50ef67fd7f7f672225b68', 'ede7c61ef3bedb10ae79b7fdc8e8f535db3f759e', '52fca8ba62f37592e9146ec24867351e760b99b5', '735e6379f66af38bb1429f4a2f69e6cfa451e8b5', 'ea665bb33b01ab5b928080c176b2229a0116c722', '800b4f74ec3241af81b81b8f91e73dfcb8fc3fe8', 'f300c169b835e3132baf1a81333d23794375e954', 'b9fda0e2a56c17cbe97e621621b78fd5d051564c', 'c161d6bfb3812b1871dc212ee4d24807bee30516', '1c4bd4091f02c4208a831e4173592cf7112efa34', '2f0ddd26f8cd82fd91d453e6089696b2d2fc1364', '0ff4f960540089dce2dcc92ea50483c18655ade2', '3f2f47f458c9e312dc19f5919e8c4ac0e44d2e11', '64d08ab0c6df800af1f1b4473dc7d894dc587349', '6d26a31f7b1a7248959163e9efebb4939f108a56', 'bcb131bf8fd20aad6f3d5a143f3c1553dd38d903', '4cb6332a58929f2222a66b16042ba8fff20f2ca9', '917532950c6e5d5f4327a258189bf31f2b6920e6', '5915a281188571a5f8533d94b881085d4190823e', '2929b0cbab67b3e00f63b7ac47bdf905f16af620', '9d2623f471b2a75c0afb9e7a56b079070e3237dd', '2c7ea4d71e96ffbe2ea2597533524ec48568d301', '1b7c7286a9f13e6747090baac30488f76972c39a', '7fd5809e73d6bad87410a61c730c103cb0184428', 'e0b8b6154e7df5d53ca2892eaf39ad16c9b2b0b4', '9a767e96bbcc36ba8f7d1113efae2d4d96a25872', 'be83a3f4e40af6d542b321dd30f48da6d4faf26d', '4d534b0bb01e3d73481e74007b80ce852fc33c8f', '5c92305e42265e4c0f7719ddba5d95b5ed5fa76d', 'dde4bc7b125bcd247ddb505a87e4c1f1477053f4', 'c1306c750296a863bbcf8efdd8212b7081c48ecc', '879ebc70f8876f85d89b55cca65f07aa9ce3d4cf']},
                    'wss4j': {'wss4j-dom': ['3ce9743ee83a2cbcce6474d0302356aef2427e2f', '421d9c3992241386d8edd5b4f7683b49c920a5c5']},
                    'helix': {'cluster-manager-core': ['8a9999c4e19e2480135f9151750dd0ee4011978a', 'afbe9c272d0b993d17b56eae68a433631973975f', '23234e70def3e192109fe1024fcfa60f6f3921db', '9e3153f03fc3279c9ec306e18d020f933968d6c2', 'c212c4daaa43c7cde24a8ca253030a008ca290cf', '790d35ad924b80f1429f2234479551935465a5e3', '8dc2d713e374069ce5cea0d2f765053214338eef', '130ee68efc392f7fdf995bbe63a6d3b35db14ca8', 'ea6048e8685bd17cc155efc1b2dc49fc66828fb1']},
                    'pdfbox': {'fontbox': ['5a8f776feba3be7cf07ee0b369121403f3bbb348', '7388792d8bf135b9533fd98c91fe7877c1220b3d', 'c5a3ce4e77947ca0977497474d49dc7fc465ad67'],
                               'pdfbox': ['503016bea214c5f95f5af1035b5e7052fbc19eae']},
                    'nifi': {'nifi': ['8cd461e276872f56951b5f660732a8fe229ee5ad', 'd2c1144870694876552dbf5d487d6cb415223fe9', 'e713258be3c2aa2dc75d860bb14d238268e8dc96',
                                      '037f36dd98833d6524e6e8c6c6b1942d7fafbcbb', '51b34a060ca9b59509360d5eb57a8ac325023142', 'fbfebf622d45d0ae972b9e1c47c617afdb8dc978',
                                      '2c2d39c7a24dc77a84e1e095280239e0d56c8357', 'd926aca951b8169b0c32a583a178dedb6e1dc605', 'a738be8f27e86fab7cf8c7bd23285fb9cb016cad',
                                      '4b852ebc651e2af7e9ba8b72494b661a86400993', 'be16371b20eeb94c90cf369917325c76c3549e1c', '4e85e34c319c847632574c9589b3aa0fdbc355b6',
                                      '3a0cb2d63404210da1b4b6827bec84f87166f60b', '4a49ba7f706f2fe7c9ef77524e9dc1353c238ec8', '0133f8471864efc0c316048b5a26e9d12351bab9',
                                      '8242417388bdfcd63cc80214b1dd1dd9c29382f5', 'f06d21fff8e118a0c28363ef5601b676f01e40c3', 'dd879f2324a24e465bfe9cf865282eb8dedcfa2f',
                                      '6488f3ca3d896e3eedb8f0274a6831fbc0b15319', 'e63268af04b131a4a216b15736a221762476ce20', '373f470b6d4c6456d2779e5ff47d2a05a7b2cdeb',
                                      '93a121044b1a7efcfc3023178fb39f2f44ad836c', '0211d0d71561fb63df4a06cd7b1a3b430b7a3e6c', 'e8134870fda7b2b8eac4033b6c9217ae2839f04c',
                                      '58ea7af9a73deadba2b57d5c30f73179e56622c4', '13cd2a67c89e2c08880247c5837360f370fc9922', '29b4e56a61dc7125e10d7e5d70a0123485717b4d',
                                      '421ad8fb133d3bab32bc20d98011e9dfa0caff99', 'ce16aab6c57a5b3d771149a1720471b980cf5a1c', '3045a52e354dd1f4cec380747b3d9cd6b1feba56',
                                      '97f33d5c51dfd5178c10ad88fb3701f363ae39a4', 'a1af29eca06fa56903ca2fa28945a0f922d6e8e9', 'bbacc3d8caf55a7773797208cc744debd11cf1bc',
                                      'b31c76bf30f847842e3ef1c6f928b2e93f517b34', '6fc52a4e9977cc219430f5c8e0e7aa41f7043066']}
                    }

CUSTOM_RULE_PROBLEMS = {'commons-digester': ['src/checkstyle/fileupload_basic.xml'],
                        'mahout': ['mahout-pmd-ruleset.xml']}


class PomPom:
    """
    Parses effective POM output from mvn help:effective-pom.

    We discrern between different POMs in one repository because each one has its own sourceDirectory and possible excludes.
    """

    def find_file(self, needle):
        if '..' in needle:
            needle = needle.replace('..', '')
        for root, dirs, files in os.walk(self.basedir):
            for file in files:
                filepath = os.path.join(root, file)
                if filepath.endswith(needle):
                    return filepath

    def __init__(self, basedir, project_name, revision_hash):
        self.basedir = basedir
        self.project_name = project_name
        self.revision_hash = revision_hash

        if not self.basedir.endswith('/'):
            self.basedir += '/'

        if project_name in CUSTOM_POM_PATHS.keys():
            for custom_dir, revisions in CUSTOM_POM_PATHS[project_name].items():
                if revision_hash in revisions:
                    self.basedir += custom_dir
                    if not self.basedir.endswith('/'):
                        self.basedir += '/'

        self.poms = {}  # holds state for each POM of the repository

    def _relative_path(self, path):
        if '${project.parent.basedir}' in path:
            path = path.replace('${project.parent.basedir}', '')
        if '${workspace.root.dir}' in path:
            path = path.replace('${workspace.root.dir}', '')
        return path.replace(self.basedir, '')

    def _read_pmd_rules(self, rel_path_file):
        """The remote file could also be a ruleset."""

        groups_expanded = False

        # if self.project_name in CUSTOM_PATHS:
        #     if rel_path_file in CUSTOM_PATHS[self.project_name].keys():
        #         file1 = self.basedir + rel_path_file
        #         file2 = self.basedir + CUSTOM_PATHS[self.project_name][rel_path_file]['new_file']

        #         print('replacing')
        #         if not os.path.isfile(file1) and os.path.isfile(file2):
        #             print('replacing {} with {}'.format(rel_path_file, CUSTOM_PATHS[self.project_name][rel_path_file]['new_file']))
        #             rel_path_file = CUSTOM_PATHS[self.project_name][rel_path_file]['new_file']

#                if self.revision_hash in CUSTOM_PATHS[self.project_name][rel_path_file]['revisions']:

        rules = set()
        file = self.basedir + rel_path_file

        if not os.path.isfile(self.basedir + rel_path_file):
            found = self.find_file(rel_path_file)
            if found:
                print('replacing {} with {}'.format(file, found))
                file = found

        # group expansion for files in the form ruleset>/rulesets/braces.xml</ruleset>
        if not os.path.isfile(file):
            print('no such file {}, trying group expansion'.format(file))
            category = rel_path_file.split('/')[-1].split('.')[0].lower()
            if category in PMD_OLD_RULESETS.keys():
                groups_expanded = True
                rules = set()
                # 1. get rules from category
                pmd_names = PMD_OLD_RULESETS[category]

                for pmd_name in pmd_names.split(','):
                    k = pmd_name.strip()
                    if k in PMD_NAME_TO_SM.keys():
                        rules.add(PMD_NAME_TO_SM[k])
            else:
                print('[{}] file {} ({}), could not find category {}'.format(self.revision_hash, file, rel_path_file, category))
                if self.project_name in CUSTOM_RULE_PROBLEMS.keys() and rel_path_file in CUSTOM_RULE_PROBLEMS[self.project_name]:
                    groups_expanded = True
                    return [], groups_expanded
                else:
                    raise

            return rules, groups_expanded

        doc = etree.parse(file)
        root = doc.getroot()

        ns = {}
        if root.nsmap:
            ns = {'m': root.nsmap[None]}  # root.nsmap returns the dict with default namespace as None

        # this is only here because of the namespaces
        def query_ns(obj, path, ns):
            if ns:
                return obj.xpath(path, namespaces=ns)
            else:
                return obj.xpath(path.replace('m:', ''))

        for rule in query_ns(doc, '//m:rule', ns):

            # some rules do not have a ref because they are fully custom
            # we can not have them in our data because they will not be available in the Sourcemeter PMD rulesets
            # therefore we skip them
            if 'ref' not in rule.attrib.keys():
                continue

            # this handles single rules, e.g., <rule ref="rulesets/java/comments.xml/CommentSize">
            if not rule.attrib['ref'].endswith('.xml'):
                k = rule.attrib['ref'].split('/')[-1]
                if k in PMD_NAME_TO_SM.keys():
                    rules.add(PMD_NAME_TO_SM[k])
                continue

            # if this fails that is critical, that means we have hit an unknown category
            category = rule.attrib['ref'].split('/')[-1].split('.')[0]

            # rule expansion from category
            try:
                pmd_names = PMD_OLD_RULESETS[category]
            except KeyError as e:
                print('ruleset {} not found in [{}]'.format(category, ','.join(PMD_OLD_RULESETS.keys())))
                raise

            for pmd_name in pmd_names.split(','):
                k = pmd_name.strip()
                if k in PMD_NAME_TO_SM.keys():
                    rules.add(PMD_NAME_TO_SM[k])

            for exclude in query_ns(rule, 'm:exclude', ns):
                k = exclude.attrib['name']
                if k in PMD_NAME_TO_SM.keys() and PMD_NAME_TO_SM[k] in rules:
                    rules.remove(PMD_NAME_TO_SM[k])

        if not rules:
            groups_expanded = True
            print('empty pmd rules for file {}'.format(rel_path_file))

        return rules, groups_expanded

    def _replace_parent_in_pom(self, pomfile):
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}

        # I really whish I would not have to do this
        with open(pomfile, 'rb') as f:
            data = f.read().decode('utf-8', 'ignore')

        doc = etree.fromstring(data.encode('utf-8'))

        gnode = doc.find('m:parent/m:groupId', namespaces=ns)
        anode = doc.find('m:parent/m:artifactId', namespaces=ns)
        vnode = doc.find('m:parent/m:version', namespaces=ns)
        rnode = doc.find('m:parent/m:relativePath', namespaces=ns)

        group_id = ''
        artifact_id = ''
        version = ''
        if gnode is not None:
            group_id = gnode.text
        if anode is not None:
            artifact_id = anode.text
        if vnode is not None:
            version = vnode.text

        # replacement rules here
        replacement = []
        if group_id == 'org.apache.commons' and artifact_id == 'commons':
            artifact_id = 'commons-parent'
            replacement.append({'old': 'commons', 'new': artifact_id})
            anode.text = artifact_id

        if group_id == 'org.apache.commons' and artifact_id == 'commons-sandbox':
            artifact_id = 'commons-sandbox-parent'
            replacement.append({'old': 'commons-sandbox', 'new': artifact_id})
            anode.text = artifact_id

        if group_id == 'org.apache.commons' and artifact_id == 'commons-sandbox-parent' and version == '1.0-SNAPSHOT':
            new_version = '1'
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version
            version = new_version

        if group_id == 'org.apache.opennlp' and artifact_id == 'opennlp-reactor':
            artifact_id = 'opennlp'
            replacement.append({'old': 'opennlp-reactor', 'new': artifact_id})
            anode.text = artifact_id

        # not working
        # if pomfile.endswith('invertedindex/pom.xml') and group_id == 'org.apache.kylin' and artifact_id == 'kylin' and version == '0.7.1-SNAPSHOT':
        #     new_version = version.replace('-SNAPSHOT', '-incubating-SNAPSHOT')
        #     replacement.append({'old': version, 'new': new_version})
        #     vnode.text = new_version
        #     version = new_version

        # snapshot is probably not available anymore but only if it does not refer to a local pom via relativePath
        if '-SNAPSHOT' in version and rnode is None:
            new_version = version.replace('-SNAPSHOT', '')
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version
            version = new_version

        # mahout has parent pointing to 0.1 but only 0.2 is in maven repository
        # Failure to find org.apache.mahout:mahout:pom:0.2-SNAPSHOT
        # if group_id == 'org.apache.wss4j' and artifact_id == 'wss4j-parent'

        # streams
        if group_id == 'org.apache.streams' and artifact_id == 'streams-master' and version in ['0.1-SNAPSHOT', '0.1']:
            new_version = '0.1-incubating'
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version
            version = new_version

        if group_id == 'org.apache.streams' and artifact_id == 'streams-master' and version in ['0.2-SNAPSHOT', '0.2']:
            new_version = '0.2-incubating'
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version
            version = new_version

        if group_id == 'org.apache.streams' and artifact_id == 'streams-master' and version in ['0.3-SNAPSHOT', '0.3']:
            new_version = '0.3-incubating'
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version
            version = new_version

        if group_id == 'org.apache.streams.osgi-components' and artifact_id == 'streams-osgi-components' and version in ['0.1-SNAPSHOT', '0.1']:
            new_version = '0.1-incubating'
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version
            version = new_version

        # 1.0 is invalid only 1 is valid in this case
        if group_id == 'org.apache.commons' and artifact_id == 'commons-parent' and '.' in version:
            new_version = version.split('.')[0]
            replacement.append({'old': version, 'new': new_version})
            vnode.text = new_version

        if replacement:
            with open(pomfile, 'wb') as f:
                f.write(etree.tostring(doc))
        return replacement

    def preflight_check(self):
        # we may have a custom pom name
        if self.project_name in CUSTOM_POM_NAMES.keys():
            for custom_name, revisions in CUSTOM_POM_NAMES[self.project_name].items():
                if self.revision_hash in revisions:
                    print('copy {} to pom.xml'.format(custom_name))
                    shutil.copy(self.basedir + '/' + custom_name, self.basedir + '/pom.xml')

        # the main file might not be there because the revision might change another pom.xml
        if not os.path.isfile(os.path.normpath(self.basedir + '/pom.xml')):
            raise OSError(os.path.normpath(self.basedir + '/pom.xml') + ' not found')

    def create_effective_pom(self):
        # call help:effective-pom to generate the effective pom the project uses
        r = subprocess.run(['mvn', 'help:effective-pom', '-B', '-U'], cwd=self.basedir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        replacements = []
        out = r.stdout

        # if this did not work we try to replace stuff
        if r.returncode != 0:

            # but only in the main pom.xml
            replacements = self._replace_parent_in_pom(self.basedir + '/pom.xml')
            r2 = subprocess.run(['mvn', 'help:effective-pom', '-B', '-U'], cwd=self.basedir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out = r2.stdout
            # if we still error we bail
            if r2.returncode != 0:
                raise MavenError(r2.stdout.decode('utf-8'))

        return out, replacements

    def parse_effective_pom(self, file):
        """
        Read Pom from passed file (effective pom).

        The file can consist of multiple POMs via a top level <projects> in the xml string, those are
        translated to idents via their groupId and artifactId which then hold a separate state for each
        pom.
        """
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}

        # I really whish I would not have to do this
        # a) we are discarding every line not starting included in the xml because help:effective-pom outputs more than the xml to stdout
        # b) we are ignoring non utf-8 chars because some projects have them in utf-8 encoded xml files
        data = ''
        in_xml = False
        multi_project = False
        for line in file.decode('utf-8', 'ignore').split('\n'):
            if line.strip().startswith('<?xml'):
                in_xml = True
            if line.strip().startswith('<projects>'):
                multi_project = True
            if in_xml:
                data += line
            # closing tag is dependent on multi project pom
            if not multi_project and line.strip().startswith('</project>'):
                in_xml = False
            if multi_project and line.strip().startswith('</projects>'):
                in_xml = False

        # with open(file, 'rb') as f:
        #     for line in f.readlines():
        #         if line.decode('utf-8', 'ignore').strip().startswith('<'):
        #             data += line

        doc = etree.fromstring(data.encode('utf-8'))

        for project in doc.xpath('//m:project', namespaces=ns):
            gid = project.find('m:groupId', namespaces=ns)
            aid = project.find('m:artifactId', namespaces=ns)
            ver = project.find('m:version', namespaces=ns)

            if gid is not None:
                ident = gid.text
            else:
                ident = 'unknown'

            if aid is not None:
                ident += ':' + aid.text
            else:
                ident += ':unknown'

            if ver is not None:
                ident += '-' + ver.text
            else:
                ident += '-unknown'

            if ident in self.poms.keys():
                raise Exception('duplicate project ident: {}'.format(ident))

            # set defaults for this project
            self.poms[ident] = {'use_pmd': False,
                                'use_checkstyle': False,
                                'use_findbugs': False,
                                'use_spotbugs': False,
                                'use_sonarcube': False,
                                'use_errorprone': False,
                                'custom_rule_files': set(),
                                'exclude_roots': set(),
                                'excludes': set(),
                                'includes': set(),
                                'include_tests': False,
                                'exclude_from_failure': set(),
                                'language': 'java',
                                'rules': set(),
                                'minimum_priority': 5,
                                'source_directory': None,
                                'test_source_directory': None,
                                'plugin_build': 0,
                                'plugin_reporting': 0,
                                }
            # we just want to know if it is there
            if len(project.xpath('//m:plugins/m:plugin[m:artifactId = "maven-checkstyle-plugin"]', namespaces=ns)) > 0:
                self.poms[ident]['use_checkstyle'] = True
            if len(project.xpath('//m:plugins/m:plugin[m:artifactId = "findbugs-maven-plugin"]', namespaces=ns)) > 0:
                self.poms[ident]['use_findbugs'] = True
            if len(project.xpath('//m:plugins/m:plugin[m:artifactId = "spotbugs-maven-plugin"]', namespaces=ns)) > 0:
                self.poms[ident]['use_spotbugs'] = True
            # taken from: https://github.com/apache/wss4j/blob/trunk/pom.xml#L248
            if len(project.xpath('//m:path[m:groupId = "com.google.errorprone"]', namespaces=ns)) > 0:
                self.poms[ident]['use_errorprone'] = True
            
            if len(project.xpath('//m:dependency[m:groupId = "com.google.errorprone"]', namespaces=ns)) > 0:
                self.poms[ident]['use_errorprone'] = True

            # detects sonar inclusion for maven-reporting
            # taken from: https://github.com/apache/helix/blob/master/pom.xml#L814
            if len(project.xpath('//m:plugins/m:plugin[m:groupId = "org.codehaus.sonar-plugins"]', namespaces=ns)) > 0:
                self.poms[ident]['use_sonarcube'] = True

            for sd in project.xpath('m:build/m:sourceDirectory', namespaces=ns):
                self.poms[ident]['source_directory'] = self._relative_path(sd.text)

            for td in project.xpath('m:build/m:testSourceDirectory', namespaces=ns):
                self.poms[ident]['test_source_directory'] = self._relative_path(td.text)

            # early return for not having the plugin
            if len(project.xpath('//m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns)) == 0:
                continue

            # if we find maven plugin we use pmd and set the default maven plugin rules
            self.poms[ident]['use_pmd'] = True
            self.poms[ident]['rules'] = set(DEFAULT_RULES_MAVEN_CLEANED)

            # how often does the plugin appear in build and reporting sections
            self.poms[ident]['plugin_build'] = len(project.xpath('m:build/m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns))
            self.poms[ident]['plugin_reporting'] = len(project.xpath('m:reporting/m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns))

            for plugin in project.xpath('m:reporting/m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns) + project.xpath('m:build/m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns) + project.xpath('m:reporting/m:pluginManagement/m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns) + project.xpath('m:build/m:pluginManagement/m:plugins/m:plugin[m:artifactId = "maven-pmd-plugin"]', namespaces=ns):
                mp = plugin.find('m:configuration/m:minimumPriority', namespaces=ns)
                lang = plugin.find('m:configuration/m:language', namespaces=ns)
                sr = plugin.find('m:configuration/m:compileSourceRoots/m:compileSourceRoot', namespaces=ns)
                tr = plugin.find('m:configuration/m:testSourceRoots/m:testSourceRoot', namespaces=ns)
                inclt = plugin.find('m:configuration/m:includeTests', namespaces=ns)
                version = plugin.find('m:version', namespaces=ns)

                if mp is not None:
                    self.poms[ident]['minimum_priority'] = mp.text
                if lang is not None:
                    self.poms[ident]['language'] = lang.text.lower()
                if sr is not None:
                    # safety exception for conflicting source_directories if the plugin is defined in reporting and build
                    if self.poms[ident]['source_directory'] and self.poms[ident]['source_directory'] != sr.text:
                        raise Exception('duplicate source directory {} in {} this happens if the plugin defines two source directories in build or reporting'.format(self.project_name, self.revision_hash))
                    self.poms[ident]['source_directory'] = sr.text
                if tr is not None:
                    self.poms[ident]['test_source_directory'] = tr.text
                if inclt is not None and inclt.text.lower() == 'true':
                    self.poms[ident]['include_tests'] = True
                if version is not None:
                    self.poms[ident]['version'] = version.text

                # this is a properties file not rule defs: https://maven.apache.org/plugins/maven-pmd-plugin/examples/violation-exclusions.html
                # also probably not in reporting but build
                for efr in plugin.xpath('m:configuration/m:excludeFromFailureFile', namespaces=ns):
                    self.poms[ident]['exclude_from_failure'].add(efr.text)

                for rs in plugin.xpath('m:configuration/m:rulesets/m:ruleset', namespaces=ns):
                    self.poms[ident]['custom_rule_files'].add(self._relative_path(rs.text))

                for exclr in plugin.xpath('m:configuration/m:excludeRoots/m:excludeRoot', namespaces=ns):
                    self.poms[ident]['exclude_roots'].add(self._relative_path(exclr.text))

                for exclf in plugin.xpath('m:configuration/m:excludes/m:exclude', namespaces=ns):
                    for exfile in [d.strip() for d in exclf.text.split(',')]:
                        if exfile:
                            self.poms[ident]['excludes'].add(exfile)

                for inclf in plugin.xpath('m:configuration/m:includes/m:include', namespaces=ns):
                    self.poms[ident]['includes'].add(inclf.text)

                # remove default maven rules in case of custom defined rules
                if self.poms[ident]['custom_rule_files']:
                    self.poms[ident]['rules'] = set()

                custom_files = set()
                for custom_ruleset in self.poms[ident]['custom_rule_files']:
                    crules, groups_expanded = self._read_pmd_rules(custom_ruleset)
                    if not groups_expanded:
                        custom_files.add(custom_ruleset)
                    self.poms[ident]['rules'].update(crules)
                self.poms[ident]['custom_rule_files'] = custom_files
        return self.poms
